"""Adapter registry: auto-discovers all *adapter.py modules in this package."""

import importlib
import os
import pkgutil

_ADAPTERS = {}


def _load():
    if _ADAPTERS:
        return _ADAPTERS
    here = os.path.dirname(os.path.abspath(__file__))
    for mod in pkgutil.iter_modules([here]):
        if mod.name.endswith("_adapter"):
            try:
                module = importlib.import_module(f"{__name__}.{mod.name}")
                cls = getattr(module, "Adapter", None)
                if cls is not None:
                    _ADAPTERS[cls.id] = cls
            except Exception as e:
                print(f"  [adapters] failed to load {mod.name}: {e}")
    return _ADAPTERS


def get_adapter_classes():
    return _load()


def get_adapter(id: str):
    return _load().get(id)
