# SPDX-License-Identifier: Apache-2.0
# ezdxf's factory stubs carry Unknown in their signatures (DEC-IO-005).
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportPrivateImportUsage=false
"""Writes `part.dxf` of this case: research 21 test 1's rectangle 100 x 60 from (0, 0) with four
fillets of radius 5, one closed LWPOLYLINE with bulges, in millimetres ($INSUNITS 4).

Run from the repository root: `uv run python testdata/zoo/profile-rectangle-fillets/make_part.py`.
The job tests call `write_part` for variants (another `$INSUNITS`)."""

import math
from pathlib import Path

import ezdxf

# A quarter-circle bulge, b = tan(phi/4) for phi = 90 degrees (research 01, Curves, Bulge).
_QUARTER = math.tan(math.radians(90.0) / 4.0)
_POINTS = [
    (5, 0, 0),
    (95, 0, _QUARTER),
    (100, 5, 0),
    (100, 55, _QUARTER),
    (95, 60, 0),
    (5, 60, _QUARTER),
    (0, 55, 0),
    (0, 5, _QUARTER),
]


def write_part(path: Path, insunits: int = 4) -> None:
    """The rectangle with fillets as a DXF at `path`; `insunits` 0 states no unit."""
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = insunits
    doc.modelspace().add_lwpolyline(_POINTS, format="xyb", close=True)
    doc.saveas(path)


if __name__ == "__main__":
    write_part(Path(__file__).with_name("part.dxf"))
