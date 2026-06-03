"""Declarative schema for SettingsBridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Property, Slot


@dataclass(frozen=True)
class SettingDef:
    qml_name: str                                   # property name
    state_owner: str                                # '_input' | '_motor' | '_camera' | '_system'
    state_attr: str                                 # field on the state dataclass
    config_key: str                                 # configStore key
    py_type: type                                   # int | float | bool | str
    notify: str                                     # name of the Signal attribute on the class
    lower: Any = None                               # numeric clamp lower bound
    upper: Any = None                               # numeric clamp upper bound
    decimals: int | None = None                     # decimals for float clamp
    allowed: tuple = field(default_factory=tuple)   # str enum constraint


def _setter_name(qml_name: str) -> str:
    return "set" + qml_name[0].upper() + qml_name[1:]


def _make_property(spec: SettingDef, signal):
    def getter(self):
        return getattr(getattr(self, spec.state_owner), spec.state_attr)
    return Property(spec.py_type, getter, notify=signal)


def _make_slot(spec: SettingDef):
    """Return a slot that resolves the bound signal."""
    if spec.allowed:
        def setter(self, v):
            self._set_allowed_state_setting(
                getattr(self, spec.state_owner),
                spec.state_attr,
                spec.config_key,
                v,
                spec.allowed,
                getattr(self, spec.notify),
            )
    elif spec.py_type is int and (spec.lower is not None or spec.upper is not None):
        lo, hi = spec.lower, spec.upper
        def setter(self, v):
            self._set_state_setting(
                getattr(self, spec.state_owner),
                spec.state_attr,
                spec.config_key,
                self._clamped_int(v, lo, hi),
                getattr(self, spec.notify),
            )
    elif spec.py_type is float and (spec.lower is not None or spec.upper is not None):
        lo, hi, dp = spec.lower, spec.upper, spec.decimals
        def setter(self, v):
            self._set_state_setting(
                getattr(self, spec.state_owner),
                spec.state_attr,
                spec.config_key,
                self._clamped_float(v, lo, hi, dp),
                getattr(self, spec.notify),
            )
    else:
        def setter(self, v):
            self._set_state_setting(
                getattr(self, spec.state_owner),
                spec.state_attr,
                spec.config_key,
                v,
                getattr(self, spec.notify),
            )

    setter.__name__ = _setter_name(spec.qml_name)
    return Slot(spec.py_type)(setter)


def register_settings(specs: list[SettingDef]):
    """Class decorator: Install Property + Slot per spec."""
    def decorator(cls):
        ns = dict(cls.__dict__)
        for spec in specs:
            if spec.notify not in ns:
                raise RuntimeError(
                    f"SettingsBridge: missing notify signal {spec.notify!r} for {spec.qml_name!r}"
                )
            sig = ns[spec.notify]
            ns[spec.qml_name] = _make_property(spec, sig)
            ns[_setter_name(spec.qml_name)] = _make_slot(spec)
        return type(cls.__name__, cls.__bases__, ns)
    return decorator
