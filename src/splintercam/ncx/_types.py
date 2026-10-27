# SPDX-License-Identifier: Apache-2.0
"""The writer's and the call's types (SPEC, Public interface)."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProgramInfo:
    """The NC program's name and number."""

    name: str  # NCX PROGRAM NAME
    number: int  # NCX NUMBER


@dataclass(frozen=True, slots=True)
class NcxSection:
    """One operation's lines in the NCX text."""

    operation: str  # "operation <index> (<name>)", index from 1 (model REQ-MDL-027)
    first_line: int  # 1-based line of its SECTION block
    last_line: int  # 1-based line of its last move (DEC-NCX-011)
    round_limit_mm: float  # the reserve share of its tol (D-149), for ROUND_LIMIT later


@dataclass(frozen=True, slots=True)
class NcxProgram:
    """One NC program: canonical NCX, ASCII, "\\n" line ends, a final "\\n"."""

    text: str
    sections: tuple[NcxSection, ...]  # the operations in program order


class NcxStep(Enum):
    """The three `ncx` steps, in the order they run (REQ-NCX-018)."""

    FORMAT = "format"
    CHECK = "check"
    COMPILE = "compile"


@dataclass(frozen=True, slots=True)
class NcxCall:
    """Where `run_ncx` runs `ncx`; every path absolute (REQ-NCX-018)."""

    executable: Path  # the pinned ncx binary
    work_dir: Path  # an empty folder the CAM made (research 27, traps 3, 4)
    ncx_file: Path  # the written NcxProgram.text
    machine_file: Path  # an NCXchange machine TOML (D-053)
    output_dir: Path  # an empty staging folder `compile` writes into
