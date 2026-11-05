"""Charge les modules sans dépendance HA (api, parser, const) dans un paquet factice."""
import importlib.util
import sys
import types
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "ekwateur"
pkg = types.ModuleType("ekw")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["ekw"] = pkg
for name in ("const", "parser", "api"):
    spec = importlib.util.spec_from_file_location(f"ekw.{name}", PKG_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"ekw.{name}"] = mod
    spec.loader.exec_module(mod)
