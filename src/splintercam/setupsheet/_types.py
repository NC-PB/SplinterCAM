# SPDX-License-Identifier: Apache-2.0
"""The setup sheet's values (setupsheet SPEC, Public interface): lengths in mm, feeds in mm/min,
speeds in 1/min, every height the tool tip's (D-154). Computed, unrounded; `render_html` rounds."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class SheetFiles:
    """The program's and the files' names, no folders (REQ-SHT-002, DEC-SHT-006)."""

    program_name: str  # NCX PROGRAM NAME
    program_number: int  # NCX NUMBER, at least 1
    ncx_file: str
    nc_files: tuple[str, ...]  # the compiled files, at least one
    machine_file: str
    job_file: str
    part_file: str


@dataclass(frozen=True, slots=True)
class Box3:
    """An axis-aligned box in the work frame."""

    min_mm: tuple[float, float, float]
    max_mm: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class SheetPoint:
    """A measurement point an operation uses: k, a and r (D-154, D-155)."""

    number: int
    axial_offset_mm: float
    register_radius_mm: float


@dataclass(frozen=True, slots=True)
class SheetTool:
    """A tool the program uses, with the points it uses, k ascending (REQ-SHT-008)."""

    number: int
    diameter_mm: float
    flute_length_mm: float
    points: tuple[SheetPoint, ...]


class Side(Enum):
    """Where an approach point lies off the stock box (REQ-SHT-011)."""

    MINUS_X = "-X"
    PLUS_X = "+X"
    MINUS_Y = "-Y"
    PLUS_Y = "+Y"
    CORNER = "corner"


@dataclass(frozen=True, slots=True)
class ApproachPoint:
    """Where the tool comes down (research 10, Method 2; REQ-SHT-010, 011)."""

    x_mm: float
    y_mm: float
    descents: int  # RAPIDs ending here below h_c
    rapid_to_mm: float  # the lowest end of those RAPIDs
    lowest_mm: float  # the lowest end of those RAPIDs and the moves along Z alone (DEC-SHT-009)
    feeds_mm_min: tuple[float, ...]  # LINEs along Z alone ending here, order of first use
    side: Side | None  # None where lowest_mm is not below the stock top
    centre_distance_mm: float | None  # P to the stock box in XY
    gap_mm: float | None  # centre_distance_mm - R


@dataclass(frozen=True, slots=True)
class WitnessMark:
    """Where a straight approach meets the cut (AQ-016 item 7; REQ-SHT-015)."""

    centre_x_mm: float  # S, the tool centre
    centre_y_mm: float
    contact_x_mm: float  # S + R·u
    contact_y_mm: float
    passes: int


@dataclass(frozen=True, slots=True)
class SheetOperation:
    """One operation of the program (REQ-SHT-009 to 012, 015, 016)."""

    name: str
    strategy: str
    tool_number: int
    point_number: int  # k
    axial_offset_mm: float  # a of point k (AQ-051)
    register_radius_mm: float  # r of point k (AQ-051)
    spindle_rpm: float
    tol_mm: float
    feeds: tuple[tuple[str, float], ...]  # the header's feed classes, in its order
    clearance_mm: float  # h_c
    retract_mm: float  # h_r
    lowest_mm: float  # the lowest end of any move
    approach_points: tuple[ApproachPoint, ...]
    witness_marks: tuple[WitnessMark, ...]
    reach: Box3 | None  # None if no move goes below h_c
    end_xy_mm: tuple[float, float] | None  # None for an operation of one RAPID (DEC-SHT-010)


@dataclass(frozen=True, slots=True)
class SetupSheet:
    """The setup sheet of one NC program of one setup."""

    files: SheetFiles
    part_box_xy_mm: tuple[float, float, float, float]  # x_min, y_min, x_max, y_max
    work_offset: int
    stock: Box3
    tools: tuple[SheetTool, ...]  # order of first use
    operations: tuple[SheetOperation, ...]  # program order
    reach: Box3 | None  # union of the operations' reach
    keep_clear: Box3 | None  # reach grown by the margin (REQ-SHT-012, AQ-056)
    holds_below_mm: float | None  # the stock gripped only below this (REQ-SHT-012)
    rapid_floor_mm: float  # the lowest h_c (REQ-SHT-013)
    reaches_stock_bottom: bool  # REQ-SHT-014
