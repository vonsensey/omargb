#!/usr/bin/env bash
# OmaRGB test runner. Python protocol/doctor/mapper tests against a mock
# OpenRGB SDK server (no hardware, no openrgb install needed), then QML
# logic probes. Exit 0 = pass.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
FAILED=0

python3 -m unittest discover -s "$HERE" -p 'test_*.py' || FAILED=1

# QML logic probes (pure .js modules, no Quickshell import needed).
for probe in "$HERE"/probe_*.qml; do
  [ -e "$probe" ] || continue
  out=$(QT_FORCE_STDERR_LOGGING=1 QT_QPA_PLATFORM=offscreen qml6 "$probe" 2>&1)
  if echo "$out" | grep -q 'ALL PROBES PASSED'; then
    echo "ok   - $(basename "$probe")"
  else
    echo "FAIL - $(basename "$probe")"
    echo "$out" | tail -20
    FAILED=1
  fi
done

echo
if [ "$FAILED" = "0" ]; then
  echo "ALL CHECKS PASSED"
  exit 0
else
  echo "CHECKS FAILED"
  exit 1
fi
