"""Utility helpers for SQLite VSS operations.

These helpers are internal; VSSService remains the public entrypoint.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


def as_vec_blob(
    vec: list[float] | np.ndarray, serializer: Callable[[list[float]], Any]
) -> Any:
    """Convert a vector to a format suitable for sqlite-vec.

    Accepts either a Python list or a NumPy array. Lists are serialized via the
    provided ``serializer`` (typically ``sqlite_vec.serialize_float32``). NumPy
    arrays are downcast to ``float32`` which supports the buffer protocol.
    """
    if isinstance(vec, list):
        return serializer(vec)
    return vec.astype(np.float32)


def distance_to_similarity(distance: float) -> float:
    """Convert a distance value into a similarity score.

    For cosine distance in sqlite-vec (0..2), convert to similarity (0..1).
    """
    return 1.0 - (distance / 2.0)
