# SPDX-License-Identifier: Apache-2.0
"""`read_dxf_contour`: a DXF drawing to one closed contour of curve rows in millimetres
(research 21; REQ-IO-001 to 030). Reads the file, resolves the unit, turns entities into rows,
chains them into one closed loop, and hands it to geometry2d's `curve_rows` (D-027, D-028, D-033).
OCCT is not used here: a DXF is read straight into NumPy curve rows, not through OCP."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ezdxf.filemanagement import readfile  # pyright: ignore[reportUnknownVariableType] (ezdxf stub)
from ezdxf.lldxf.const import DXFError

from splintercam.foundation import CANCELLED, Context, Result
from splintercam.geometry2d import Box, CurveRows, curve_rows

from . import _diagnostics as diag
from ._chain import box_of_rows, resolve_contour
from ._entities import build_rows, scan
from ._units import DrawingUnit, file_factor_mm, insunits_name, is_supported

_SEG_BITS = 16


class _Stop(Exception):  # noqa: N818 (an internal control signal, not an error condition)
    """Raised to end the import with no value; the collector already holds the diagnostics."""


@dataclass(frozen=True, slots=True)
class DxfContour:
    """One closed loop read from a DXF drawing, in millimetres (D-028, D-033)."""

    loop: CurveRows
    part_size: Box


def decode_source_id(source_id: int) -> tuple[int, int]:
    """The (entity index in model space, segment index) a row's source ID encodes (REQ-IO-016)."""
    return source_id >> _SEG_BITS, source_id & ((1 << _SEG_BITS) - 1)


def _resolve_factor(insunits: int, unit: DrawingUnit | None, collector: diag.Collector
                    ) -> float | None:  # fmt: skip
    # The millimetre factor, None for "no unit" (handled after the scan). A terminal unit error
    # (unsupported value or a conflict with the job's unit) raises _Stop (REQ-IO-005 to 008).
    if not is_supported(insunits):
        name = insunits_name(insunits)
        collector.file(diag.DXF_UNIT_UNSUPPORTED, f"$INSUNITS {name}: a unit io does not read")
        raise _Stop
    file_factor = file_factor_mm(insunits)
    if file_factor is not None:
        if unit is not None and unit.factor_mm != file_factor:
            collector.file(diag.DXF_UNIT_CONFLICT,
                           f"the file states {insunits_name(insunits)} but the job states "
                           f"{unit.name.lower()}")  # fmt: skip
            raise _Stop
        return file_factor
    return unit.factor_mm if unit is not None else None


def _no_units(loose_box: tuple[float, float, float, float] | None, collector: diag.Collector
              ) -> None:  # fmt: skip
    if loose_box is None:
        size = "no readable entities"
    else:
        size = f"{loose_box[2] - loose_box[0]:g} x {loose_box[3] - loose_box[1]:g} drawing units"
    collector.file(diag.DXF_NO_UNITS,
                   f"the file states no unit (part size {size}); give the job's unit")  # fmt: skip


def read_dxf_contour(path: Path, layer: str | None, unit: DrawingUnit | None,
                     ctx: Context) -> Result[DxfContour]:  # fmt: skip
    """Read one closed contour from the DXF at `path` (REQ-IO-001 to 030). `layer` selects one
    layer or the whole drawing (None); `unit` is used only for a file without `$INSUNITS`."""
    collector = diag.Collector()
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    try:
        document = readfile(str(path))
    except (OSError, DXFError) as error:
        collector.file(diag.DXF_UNREADABLE, f"cannot read {path}: {error}")
        return Result(None, collector.emit())
    try:
        factor = _resolve_factor(int(document.header.get("$INSUNITS", 0)), unit, collector)
        scan_result = scan(list(document.modelspace()), layer, ctx, collector)
        if layer is not None and not scan_result.any_read:
            collector.file(diag.DXF_LAYER_EMPTY, f"no readable entity on layer {layer!r}")
            raise _Stop
        if factor is None:
            _no_units(scan_result.loose_box_drawing, collector)
            raise _Stop
        rows, ids = build_rows(scan_result, factor, ctx, collector)
        if ctx.cancel.is_cancelled:
            return Result(None, (CANCELLED,))
        return _finish(resolve_contour(rows, ids, ctx, collector), ctx, collector)
    except _Stop:
        return Result(None, collector.emit())


def _finish(loop: tuple[np.ndarray, np.ndarray] | None, ctx: Context,
            collector: diag.Collector) -> Result[DxfContour]:  # fmt: skip
    if loop is None:
        raise _Stop
    built = curve_rows(loop[0], loop[1], np.array([0], dtype=np.int64), ctx)
    collector.curve_rows(built.diagnostics)
    if built.value is None or collector.has_error():
        raise _Stop
    box = box_of_rows(built.value.rows, ctx)
    collector.part_size(f"part size {box.x_max_mm - box.x_min_mm:g} x "
                        f"{box.y_max_mm - box.y_min_mm:g} mm")  # fmt: skip
    return Result(DxfContour(built.value, box), collector.emit())
