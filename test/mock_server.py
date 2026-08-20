"""A fake OpenRGB SDK server for the test suite.

Serves the fixture rig over real TCP on an ephemeral localhost port, speaking
the ORGB wire format via orgb_wire (an implementation independent of the
bridge's). Records every control packet it receives so tests can assert on
exact bytes, and can inject faults: refused connections, a protocol-0 server
that never answers version requests, mid-session device-list pushes, and
lowered protocol versions.
"""

import socket
import struct
import threading

import orgb_wire

PKT_REQUEST_CONTROLLER_COUNT = 0
PKT_REQUEST_CONTROLLER_DATA = 1
PKT_REQUEST_PROTOCOL_VERSION = 40
PKT_SET_CLIENT_NAME = 50
PKT_DEVICE_LIST_UPDATED = 100
PKT_PROFILE_LIST = 150
PKT_PROFILE_SAVE = 151
PKT_PROFILE_LOAD = 152


class MockOrgbServer:
    def __init__(self, rig, protocol=5, mute_version=False, refuse_first=0,
                 port=0, truncate_controller=False, close_after=None):
        self.rig = list(rig)
        self.protocol = protocol
        self.mute_version = mute_version
        self.refuse_first = refuse_first
        self.truncate_controller = truncate_controller  # malformed replies
        self.close_after = close_after  # close the conn after N packets
        self.received = []          # (dev_id, pkt_id, payload) control packets
        self.client_name = None
        self.profiles = ["default"]
        self.lock = threading.Lock()
        self.conn = None
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", port))
        self.listener.listen(4)
        self.port = self.listener.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        try:
            self.listener.close()
        except OSError:
            pass
        with self.lock:
            if self.conn is not None:
                try:
                    self.conn.close()
                except OSError:
                    pass

    def push_device_list_updated(self):
        with self.lock:
            if self.conn is not None:
                self.conn.sendall(orgb_wire.header(0, PKT_DEVICE_LIST_UPDATED, 0))

    def set_rig(self, rig):
        self.rig = list(rig)

    def control_packets(self, pkt_id=None):
        with self.lock:
            if pkt_id is None:
                return list(self.received)
            return [p for p in self.received if p[1] == pkt_id]

    # -- internals

    def _accept_loop(self):
        while self.running:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            if self.refuse_first > 0:
                self.refuse_first -= 1
                conn.close()
                continue
            with self.lock:
                self.conn = conn
            # One thread per connection: reconnecting clients (a restarted
            # bridge) must be served, not queued behind a dead first client.
            threading.Thread(target=self._serve_conn, args=(conn,),
                             daemon=True).start()

    def _serve_conn(self, conn):
        try:
            self._serve(conn)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            with self.lock:
                if self.conn is conn:
                    self.conn = None

    def _read_exact(self, conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise OSError("client gone")
            buf += chunk
        return buf

    def _reply(self, conn, dev_id, pkt_id, payload):
        conn.sendall(orgb_wire.header(dev_id, pkt_id, len(payload)) + payload)

    def _serve(self, conn):
        packets_seen = 0
        while self.running:
            head = self._read_exact(conn, 16)
            assert head[:4] == orgb_wire.MAGIC, "client sent bad magic"
            dev_id, pkt_id, size = struct.unpack("<III", head[4:])
            payload = self._read_exact(conn, size) if size else b""
            packets_seen += 1
            if self.close_after is not None and packets_seen > self.close_after:
                conn.close()
                return

            if pkt_id == PKT_REQUEST_PROTOCOL_VERSION:
                if not self.mute_version:
                    self._reply(conn, 0, PKT_REQUEST_PROTOCOL_VERSION,
                                struct.pack("<I", self.protocol))
            elif pkt_id == PKT_SET_CLIENT_NAME:
                self.client_name = payload.rstrip(b"\x00").decode("utf-8", "replace")
            elif pkt_id == PKT_REQUEST_CONTROLLER_COUNT:
                self._reply(conn, 0, PKT_REQUEST_CONTROLLER_COUNT,
                            struct.pack("<I", len(self.rig)))
            elif pkt_id == PKT_REQUEST_CONTROLLER_DATA:
                ver = 0
                if self.protocol >= 1 and len(payload) >= 4:
                    (ver,) = struct.unpack("<I", payload[:4])
                ver = min(ver, self.protocol)
                if dev_id < len(self.rig):
                    blob = orgb_wire.controller(self.rig[dev_id], ver)
                    if self.truncate_controller:
                        blob = blob[:len(blob) // 2]
                    self._reply(conn, dev_id, PKT_REQUEST_CONTROLLER_DATA, blob)
            elif pkt_id == PKT_PROFILE_LIST:
                body = struct.pack("<H", len(self.profiles))
                for name in self.profiles:
                    body += orgb_wire.string(name)
                self._reply(conn, 0, PKT_PROFILE_LIST,
                            struct.pack("<I", 4 + len(body)) + body)
            elif pkt_id == PKT_PROFILE_SAVE:
                name = payload.rstrip(b"\x00").decode("utf-8", "replace")
                if name and name not in self.profiles:
                    self.profiles.append(name)
                with self.lock:
                    self.received.append((dev_id, pkt_id, payload))
            else:
                if pkt_id == 1050 and dev_id < len(self.rig):
                    # Real OpenRGB reflects UpdateLEDs in controller data;
                    # mirror that so clients re-reading colors see them.
                    (count,) = struct.unpack("<H", payload[4:6])
                    colors = list(struct.unpack("<%dI" % count, payload[6:6 + 4 * count]))
                    dev = dict(self.rig[dev_id])
                    dev["colors"] = colors
                    self.rig[dev_id] = dev
                with self.lock:
                    self.received.append((dev_id, pkt_id, payload))


if __name__ == "__main__":
    # Dev rig: serve the six fixture devices on the real SDK port so the
    # plugin can be exercised on a machine with no RGB hardware at all.
    #   python3 test/mock_server.py [port]
    import sys
    import time as _time

    import orgb_rig

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 6742
    server = MockOrgbServer(orgb_rig.RIG, port=port)
    print("mock OpenRGB server on 127.0.0.1:%d (fixture rig, 6 devices)"
          % server.port, flush=True)
    try:
        while True:
            _time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()
