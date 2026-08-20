"""Doctor tests: every probe runs against a fake sysroot, no hardware."""

import os
import shutil
import socket
import tempfile
import unittest

import common

B = common.load_bridge()


def make_root(modules="", cmdline="", board="", i2c_nodes=0, udev=False):
    root = tempfile.mkdtemp(prefix="omargb-doctor-")
    os.makedirs(os.path.join(root, "proc"))
    os.makedirs(os.path.join(root, "dev"))
    os.makedirs(os.path.join(root, "sys/class/dmi/id"))
    with open(os.path.join(root, "proc/modules"), "w") as f:
        f.write(modules)
    with open(os.path.join(root, "proc/cmdline"), "w") as f:
        f.write(cmdline)
    with open(os.path.join(root, "sys/class/dmi/id/board_vendor"), "w") as f:
        f.write(board + "\n")
    for i in range(i2c_nodes):
        open(os.path.join(root, "dev/i2c-%d" % i), "w").close()
    if udev:
        rules = os.path.join(root, "usr/lib/udev/rules.d")
        os.makedirs(rules)
        open(os.path.join(rules, "60-openrgb.rules"), "w").close()
    return root


def which_yes(name):
    return "/usr/bin/" + name


def which_no(name):
    return None


class Doctor(unittest.TestCase):
    def setUp(self):
        # A listening socket = "server reachable" for the probe.
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.addCleanup(self.listener.close)
        self.dead_port = self._closed_port()

    def _closed_port(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def by_id(self, checks):
        return {c["id"]: c for c in checks}

    def test_golden_machine_all_ok(self):
        root = make_root(modules="i2c_dev 16384 0 - Live\n",
                         i2c_nodes=3, udev=True)
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(
            root=root, port=self.port, which=which_yes, device_count=6))
        for check_id in ("openrgb-installed", "server-reachable", "udev-rules",
                         "i2c-dev", "i2c-nodes", "spd5118", "devices"):
            self.assertEqual(checks[check_id]["status"], "ok", check_id)
        self.assertEqual(checks["gigabyte-acpi"]["status"], "skip")

    def test_missing_openrgb_fails_with_pacman_fix(self):
        root = make_root()
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(
            root=root, port=self.dead_port, which=which_no))
        self.assertEqual(checks["openrgb-installed"]["status"], "fail")
        self.assertIn("pacman -S openrgb", checks["openrgb-installed"]["fix"])
        self.assertEqual(checks["server-reachable"]["status"], "skip")

    def test_server_down_but_installed_is_a_distinct_warning(self):
        root = make_root(udev=True, modules="i2c_dev 1 0 - Live\n", i2c_nodes=1)
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(
            root=root, port=self.dead_port, which=which_yes))
        self.assertEqual(checks["openrgb-installed"]["status"], "ok")
        self.assertEqual(checks["server-reachable"]["status"], "warn")
        self.assertIn("autostart", checks["server-reachable"]["fix"])

    def test_missing_i2c_dev_fails_with_modprobe_fix(self):
        root = make_root(modules="ext4 12345 0 - Live\n")
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(
            root=root, port=self.port, which=which_yes))
        self.assertEqual(checks["i2c-dev"]["status"], "fail")
        self.assertIn("modprobe i2c-dev", checks["i2c-dev"]["fix"])
        self.assertIn("modules-load.d", checks["i2c-dev"]["fix"])

    def test_gigabyte_without_kernel_param_warns(self):
        root = make_root(board="Gigabyte Technology Co., Ltd.",
                         cmdline="BOOT_IMAGE=/vmlinuz root=/dev/sda1")
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(root=root, port=self.port,
                                            which=which_yes))
        self.assertEqual(checks["gigabyte-acpi"]["status"], "warn")
        self.assertIn("acpi_enforce_resources=lax", checks["gigabyte-acpi"]["fix"])

    def test_gigabyte_with_param_is_ok(self):
        root = make_root(board="Gigabyte Technology Co., Ltd.",
                         cmdline="root=/dev/sda1 acpi_enforce_resources=lax")
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(root=root, port=self.port,
                                            which=which_yes))
        self.assertEqual(checks["gigabyte-acpi"]["status"], "ok")

    def test_spd5118_loaded_warns_with_rmmod(self):
        root = make_root(modules="i2c_dev 1 0 - Live\nspd5118 1 0 - Live\n")
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(root=root, port=self.port,
                                            which=which_yes))
        self.assertEqual(checks["spd5118"]["status"], "warn")
        self.assertIn("rmmod spd5118", checks["spd5118"]["fix"])

    def test_zero_devices_on_healthy_server_warns(self):
        root = make_root(modules="i2c_dev 1 0 - Live\n", i2c_nodes=1, udev=True)
        self.addCleanup(shutil.rmtree, root)
        checks = self.by_id(B.doctor_checks(
            root=root, port=self.port, which=which_yes, device_count=0))
        self.assertEqual(checks["devices"]["status"], "warn")
        self.assertIn("loglevel", checks["devices"]["fix"])

    def test_every_check_has_the_contract_fields(self):
        root = make_root()
        self.addCleanup(shutil.rmtree, root)
        for check in B.doctor_checks(root=root, port=self.dead_port,
                                     which=which_no, device_count=None):
            self.assertIn(check["status"], ("ok", "warn", "fail", "skip"))
            self.assertTrue(check["summary"])
            self.assertIn("fix", check)


if __name__ == "__main__":
    unittest.main()
