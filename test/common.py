"""Shared test plumbing: load bin/omargb-bridge (no .py extension) as a module."""

import importlib.machinery
import importlib.util
import os

_BIN = os.path.join(os.path.dirname(__file__), "..", "bin", "omargb-bridge")


def load_bridge():
    loader = importlib.machinery.SourceFileLoader("omargb_bridge", _BIN)
    spec = importlib.util.spec_from_loader("omargb_bridge", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod
