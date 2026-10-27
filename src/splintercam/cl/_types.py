# SPDX-License-Identifier: Apache-2.0
"""The toolpath record's types: an operation header above its moves as columns (research 26,
Structure; DEC-CL-001). Built directly they are unchecked; `make_operation` checks them."""

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray


class MoveKind(IntEnum):
    """What a move is; slice subset of research 26, Move."""

    RAPID = 0
    LINE = 1
    ARC = 2


class Role(IntEnum):
    """Why a move is there; slice subset of research 26, Roles (ISO 14649, SRC-113)."""

    LINK = 0
    APPROACH = 1
    CUT = 2
    RETRACT = 3


NO_FEED_CLASS = -1  # the feed class of a RAPID


@dataclass(frozen=True, slots=True)
class ClHeader:
    """One operation's header (research 26, operation header; slice subset)."""

    name: str  # NCX SECTION, model's operation name
    note: tuple[str, ...]  # NCX COMMENT lines after the name (feature map, section 6)
    tool_number: int  # NCX TOOL=
    point_number: int  # k (D-155)
    axial_offset_mm: float  # a; the writer shifts every Z by it (D-154)
    spindle_rpm: float  # CW (research 26 subset)
    tol_mm: float  # the operation tolerance (D-029); the writer's rounding allowance
    feed_classes: tuple[tuple[str, float], ...]  # (class name, mm/min), by ClMoves.feed_class
    clearance_height_mm: float  # D-062, work frame
    retract_height_mm: float  # h_r (D-062, AQ-018): no RAPID ends below it


@dataclass(frozen=True, slots=True, eq=False)
class ClMoves:
    """n moves in order, one row each; the tool centre at the tip in the work frame (D-154)."""

    kind: NDArray[np.int8]  # (n,) MoveKind
    role: NDArray[np.int8]  # (n,) Role
    end_mm: NDArray[np.float64]  # (n, 3); row 0 is (NaN, NaN, z): along the axis only
    centre_mm: NDArray[np.float64]  # (n, 2) XY of an ARC's centre; NaN otherwise
    sweep_rad: NDArray[np.float64]  # (n,) signed, + is CCW about +Z (D-057); 0 otherwise
    feed_class: NDArray[np.int64]  # (n,) index into feed_classes; NO_FEED_CLASS for a RAPID
    link_height_mm: NDArray[np.float64]  # (n,) a RAPID's link height (D-062); NaN otherwise


@dataclass(frozen=True, slots=True, eq=False)
class ClOperation:
    """An operation: its header above its moves."""

    header: ClHeader
    moves: ClMoves


@dataclass(frozen=True, slots=True, eq=False)
class ClData:
    """One setup (D-078): its work offset and its operations in the user's order (D-126)."""

    work_offset: int  # NCX ORIGIN, an index
    operations: tuple[ClOperation, ...]
