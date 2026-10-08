# SPDX-License-Identifier: Apache-2.0
"""The machining region (research 01, Loop tree, rule 7): the loop tree's loops flattened into air
and joined on Clipper2's grid."""

from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._grid import FillRule, region_with_fill_rule
from ._loops import flatten_loops
from ._polygon import FlatRegion, RegionKind
from ._rows import CurveRows
from ._tree import loop_tree


def build_region(loops: CurveRows, kind: RegionKind, ctx: Context) -> Result[FlatRegion]:
    """The machining region of closed loops of lines and arcs: the loop tree (its diagnostics
    passed on; no region when loops cross or a grid call is refused), the side-correct flattening
    of its normalised loops, and their union on the grid with the Positive fill rule. An empty
    region carries `REGION_EMPTY`. Lines and arcs only, so the extra clearance is 0.

    Implements: REQ-G2D-118, REQ-G2D-124, REQ-G2D-162, REQ-G2D-176, REQ-G2D-235.
    """
    tree_result = loop_tree(loops, ctx)
    tree = tree_result.value
    diagnostics = list(tree_result.diagnostics)
    if tree is None or not tree_result.ok:
        return Result(None, tuple(diagnostics))
    flat = flatten_loops(tree, kind, ctx)
    joined = region_with_fill_rule(flat.region, FillRule.POSITIVE, ctx)
    diagnostics += joined.diagnostics
    if joined.value is None:
        return Result(None, tuple(diagnostics))
    if joined.value.loop_starts.size == 0:
        message = "no loop is left of the region"
        diagnostics.append(Diagnostic("REGION_EMPTY", Severity.WARNING, message))
    return Result(FlatRegion(joined.value, 0.0), tuple(diagnostics))
