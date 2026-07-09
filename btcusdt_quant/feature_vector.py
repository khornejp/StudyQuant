"""Columnar, float32-backed feature storage.

The dataset previously stored each row's features as a ``dict[str, float]``.
A 189-entry dict costs ~9-20 KB per row; across ~3M rows that dominates memory
(tens of GB). ``FeatureVector`` stores the same values as a single
``array('f')`` (4 bytes each, ~760 bytes for 189 features) aligned to a shared
canonical feature-name order, while still behaving like the old mapping:
``fv[name]``, ``fv.get(name)``, ``fv[name] = v``, ``name in fv``, ``dict(fv)``,
``fv.items()``, ``set(fv)``, ``**fv`` all work, so existing call sites are
unchanged.

Notes:
* float32: feature values are rounded to single precision. This is standard for
  ML feature storage and is what most model backends use internally anyway.
* None -> NaN: a missing (None) feature is stored as NaN (the columnar missing
  convention). ``get`` returns NaN, not None, for such entries.
* The canonical names/index are module-global and shared by every vector, so
  they cost one copy total and pickle once per stream. Pickling a vector stores
  only its float32 buffer; the names are re-linked on unpickle.
"""

from __future__ import annotations

from array import array
from collections.abc import Mapping
from math import nan
from typing import Iterator, Sequence

# Canonical order is bound once by dataset at import time via bind_canonical().
_CANON_NAMES: tuple[str, ...] = ()
_CANON_INDEX: dict[str, int] = {}


def bind_canonical(names: Sequence[str]) -> None:
    """Bind the canonical feature-name order shared by all FeatureVectors.

    Called once by the dataset module with FEATURE_NAMES. Idempotent for the
    same names; rebinding a different order is refused so pickled vectors stay
    consistent across processes.
    """
    global _CANON_NAMES, _CANON_INDEX
    names = tuple(names)
    if _CANON_NAMES and _CANON_NAMES != names:
        raise RuntimeError("FeatureVector canonical names already bound to a different order")
    _CANON_NAMES = names
    _CANON_INDEX = {name: i for i, name in enumerate(names)}


def _f(value: object) -> float:
    if value is None:
        return nan
    return float(value)  # type: ignore[arg-type]


class FeatureVector(Mapping):
    """A read/write mapping of feature name -> float, backed by float32 array."""

    __slots__ = ("_values",)

    def __init__(self, values: "array[float]") -> None:
        self._values = values

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "FeatureVector":
        """Build from a full feature dict (keys must be the canonical set;
        missing names default to NaN, extra names are ignored)."""
        get = data.get
        return cls(array("f", [_f(get(name)) for name in _CANON_NAMES]))

    # -- read --------------------------------------------------------------
    def __getitem__(self, key: str) -> float:
        i = _CANON_INDEX.get(key)
        if i is None:
            raise KeyError(key)
        return self._values[i]

    def get(self, key: str, default: object = None) -> object:  # type: ignore[override]
        i = _CANON_INDEX.get(key)
        return self._values[i] if i is not None else default

    def __contains__(self, key: object) -> bool:
        return key in _CANON_INDEX

    def __iter__(self) -> Iterator[str]:
        return iter(_CANON_NAMES)

    def __len__(self) -> int:
        return len(_CANON_NAMES)

    # -- write (in place; only canonical names) ----------------------------
    def __setitem__(self, key: str, value: object) -> None:
        i = _CANON_INDEX.get(key)
        if i is None:
            raise KeyError(f"unknown feature {key!r}")
        self._values[i] = _f(value)

    # -- equality (compare as a plain mapping) -----------------------------
    def __eq__(self, other: object) -> bool:
        if isinstance(other, FeatureVector):
            return self._values == other._values
        if isinstance(other, Mapping):
            return dict(self) == dict(other)
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    __hash__ = None  # type: ignore[assignment]

    # -- pickle: store only the float buffer; re-link shared names ----------
    def __reduce__(self):
        return (_rebuild_feature_vector, (self._values,))


def _rebuild_feature_vector(values: "array[float]") -> FeatureVector:
    return FeatureVector(values)
