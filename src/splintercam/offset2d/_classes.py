# SPDX-License-Identifier: Apache-2.0
"""The class of every source ID (research 02, Inputs and outputs; D-059)."""

import enum
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


class EdgeClass(enum.IntEnum):
    """What an input edge bounds, in the order of the tie of D-059: material wins."""

    MATERIAL = 0
    CLEARED = 1
    AIR = 2


@dataclass(frozen=True, slots=True)
class SourceClasses:
    """The class of every source ID: `ids` strictly ascending, `classes` an `EdgeClass` each."""

    ids: NDArray[np.int64]
    classes: NDArray[np.int8]


def check_classes(classes: SourceClasses, source_ids: NDArray[np.int64]) -> None:
    """Every source ID has a class, and the classes are well formed; else `ValueError`.

    Implements: REQ-OFF-013.
    """
    ids, kinds = np.asarray(classes.ids), np.asarray(classes.classes)
    if ids.ndim != 1 or kinds.shape != ids.shape or np.any(np.diff(ids) <= 0):
        raise ValueError("SourceClasses needs ascending IDs and one class each")
    if not np.isin(kinds, [int(c) for c in EdgeClass]).all():
        raise ValueError("every class must be an EdgeClass")
    if not np.isin(source_ids, ids).all():
        raise ValueError("every source ID needs a class")
