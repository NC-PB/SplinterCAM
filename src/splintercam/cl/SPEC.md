# SPEC: cl

<!-- The toolpath record (CL data). Drafted on 2026-10-25 for plan 0007, step 4, cut to the slice (D-160): one
     setup, operations with a header and RAPID, LINE and planar ARC moves in XY, the tool centre at the tip, no
     control compensation. Helices, cycles, dwells, the golden-file serialisation and the other fields of
     research 26 come with later plans. -->

| | |
| --- | --- |
| Status | Reviewed (2026-10-26, Peter: AQ-005 to AQ-008 in `docs/agents/QUESTIONS.md`, all as recommended; plan 0007, Decisions). Choices marked "(ours)" are in `src/splintercam/cl/DECISIONS.md` |
| Layer | 2 (see architecture/modules.yaml) |
| Depends on | foundation (`Context`, `ToleranceSet`); geometry2d (`check_arc_rows`, the arc check of REQ-CL-016; AQ-006 (a)) |
| Research | [26][r26], sections The subset plan 0007 uses, Structure, Arcs and helices, Links and heights, Mapping onto NCX (for what the record must carry), Traps, Tests; [10][r10], Method (the order of the links) |
| Decisions | D-052 (structure), D-057 (arc form), D-028 (units), D-024 and D-154 (the record is the tool centre at the tip), D-062 and D-087 (link heights, G0 only above them), D-078 (setup), D-126 (operation order), D-055 (determinism); text in [docs/spike/decisions-snapshot.md](../../../docs/spike/decisions-snapshot.md) |
| Owner | Peter Burgener |

## Purpose

Holds the neutral record that a strategy writes and every later module reads: per operation a header (name, note, tool and point, spindle speed, feed classes, clearance height) above an ordered list of typed moves with a role and a feed class (D-052). Its only behaviour is to refuse a record that breaks its rules, so the NCX writer (plan 0007, step 6) and later the linker and simulation never guess what a move means. Its producers in plan 0007 are `strategies/profile` and `toolpath` (step 5); its reader is `ncx` (step 6).

## Scope

- In: one setup with its work offset and its operations in the user's order (D-078, D-126); the header fields of research 26's subset; RAPID, LINE and planar ARC in XY (|sweep| ≤ 2π, no travel); the roles LINK, APPROACH, CUT and RETRACT; feed classes by name; the link height on every RAPID (research 10, Method 5); the checks of research 26, tests 1, 2 and 5 that apply to these moves. Spindle CW, coolant on, `comp_mode` CENTER and plane XY hold for every operation, without fields (research 26 subset; DEC-CL-003); `ncx`'s tests in step 6 check the words it writes for them.
- Out, handled elsewhere: computing the moves, heights and link heights, and research 10 test 1's checks against the stock (no RAPID in the plane below h_c, no move below h_r inside the stock box grown by R): `toolpath` and `strategies/profile`, step 5; `cl` takes each link height as given. Checking user input (`model`'s `check_job`; this module's checks catch producer bugs, REQ-CL-020). Writing NCX (`ncx`, steps 6 and 7): the number printer, the measurement point's shift of Z, the rounding allowance from tol, whether the name is written as a `COMMENT` besides `SECTION`, the program's name and number, a diagnostic for a point other than k = 1 while NCX has no point words (R1-11; the record holds k as given), and the refusal of an arc with |sweep| < 2π whose printed end equals its printed start (REQ-CL-014's eps_len floor equals the NCX step of D-149, so it is no guarantee; at the machine's coarser resolution the same case is NCXchange's, D-149, DEC-CL-006).
- Later (one line each, no work): helices, other planes, cycles, dwells; the roles PLUNGE and AIR, and LINE moves with role LINK (D-087); a feed per move below its class value (D-110, D-113); `comp` and `comp_mode` CONTROL with the register radius r and its comment (D-024, D-154); `source` per move (D-054, D-059); spindle direction and coolant as fields (research 26 subset: CW and on; DEC-MDL-006); `control_tol` and `TOLERANCE` words (research 26 subset: not written); `op_id`, `setup_id`, placement, stock and fixture references; several setups and the program header; the JSON Lines serialisation for golden files and its comparison tiers (research 26, Serialisation; with the first golden case that compares the record); reserved axes, spindles and channels (D-022).
- Non-goals: rounding (D-052: float64, unrounded; NCXchange rounds, D-149); any controller knowledge (D-021, D-148); recomputing an arc's end (research 26: the record stores it).

## Public interface

Lengths in mm, angles in rad, feeds in mm/min, speeds in 1/min, float64 (D-028). Coordinates are the tool centre at the tip in the work frame of the setup (D-154; research 26, Inputs and outputs). All names are proposals (ours). No kernel. Moves are held as columns of NumPy arrays, one row per move, and checked vectorised (split rule; DEC-CL-001).

```python
from dataclasses import dataclass
from enum import IntEnum
import numpy as np
from numpy.typing import NDArray
from splintercam.foundation import Context

class MoveKind(IntEnum): RAPID = 0; LINE = 1; ARC = 2
class Role(IntEnum): LINK = 0; APPROACH = 1; CUT = 2; RETRACT = 3      # research 26, Roles (slice subset)

NO_FEED_CLASS = -1                                # the feed class of a RAPID

@dataclass(frozen=True, slots=True)
class ClHeader:                                   # research 26, operation header (slice subset)
    name: str                                     # NCX SECTION, model's operation name
    note: tuple[str, ...]                         # NCX COMMENT lines after the name (feature map, section 6)
    tool_number: int                              # NCX TOOL=
    point_number: int                             # k (D-155)
    axial_offset_mm: float                        # a; the writer shifts every Z by it (D-154)
    spindle_rpm: float                            # CW (research 26 subset)
    tol_mm: float                                 # the operation tolerance (D-029); the writer's rounding allowance
    feed_classes: tuple[tuple[str, float], ...]   # (class name, mm/min), indexed by ClMoves.feed_class
    clearance_height_mm: float                    # D-062, work frame

@dataclass(frozen=True, slots=True, eq=False)
class ClMoves:                                    # n moves in order; read-only arrays
    kind: NDArray[np.int8]                        # (n,) MoveKind
    role: NDArray[np.int8]                        # (n,) Role
    end_mm: NDArray[np.float64]                   # (n, 3); row 0 is (NaN, NaN, z): along the axis only
    centre_mm: NDArray[np.float64]                # (n, 2) XY of an ARC's centre; NaN otherwise
    sweep_rad: NDArray[np.float64]                # (n,) signed, + is CCW about +Z (D-057); 0 otherwise
    feed_class: NDArray[np.int64]                 # (n,) index into feed_classes; NO_FEED_CLASS for a RAPID
    link_height_mm: NDArray[np.float64]           # (n,) a RAPID's link height (D-062); NaN otherwise

@dataclass(frozen=True, slots=True, eq=False)
class ClOperation:
    header: ClHeader
    moves: ClMoves

@dataclass(frozen=True, slots=True, eq=False)
class ClData:                                     # one setup (D-078)
    work_offset: int                              # NCX ORIGIN, an index
    operations: tuple[ClOperation, ...]           # the user's order (D-126)

def make_operation(header: ClHeader, moves: ClMoves, ctx: Context) -> ClOperation: ...
def make_cl_data(work_offset: int, operations: tuple[ClOperation, ...], ctx: Context) -> ClData: ...
```

- `make_operation` and `make_cl_data` are the validating entries; a record built directly is unchecked, as geometry2d's `Line` and `Arc` are (ours). `make_operation` returns its arrays as read-only copies; `make_cl_data` checks every operation again, so an operation built directly cannot reach `ncx` unchecked.
- A broken record is a programming error in its producer, not user input: both functions raise `ValueError` naming the operation, the move's index and the rule (REQ-CL-020; DEC-CL-002). Neither polls `ctx.cancel`: the checks are vectorised and short (ours, DEC-CL-002).
- Starts (research 26, Move: a move starts where the previous one ended). Move 0 has no start: it begins wherever the tool change left the tool and moves along the tool axis only (research 10, Method 1 and trap 2). Move 1 starts at (unknown, unknown, z of move 0) and counts as a move that changes x and y. Every later move starts at the previous move's end.
- Preconditions inherited from geometry2d's arc check (AQ-006): radii up to 10^9 mm and coordinates in the range of geometry2d's exact predicates (`src/splintercam/geometry2d/SPEC.md`, DEC-G2D-019). An arc the producer reversed (research 22, Method 2: climb) must pass the check in the direction it is written; the producer checks it after reversing (DEC-CL-006).

## Requirements

| ID | Requirement (EARS) | Verified by | Status |
| --- | --- | --- | --- |
| REQ-CL-001 | THE cl module SHALL hold one setup as its work offset and its operations in the user's order, and an operation as a header above its moves in order (D-052, D-078, D-126). | unit: `test_operations_and_moves_keep_their_order` | Reviewed |
| REQ-CL-002 | THE operation header SHALL hold the name, the note lines, the tool number, the measurement point's number k and axial offset a, the spindle speed, the tolerance tol, the feed classes as (name, mm/min) pairs and the clearance height (research 26, The subset plan 0007 uses; feature map, section 6). | unit: `test_every_header_field_reads_back` | Reviewed |
| REQ-CL-003 | THE moves SHALL be held as the seven columns of `ClMoves`, one row per move, with the units and fill values of the interface above (research 26, Move; DEC-CL-001). | unit: `test_the_profile_record_has_the_seven_columns` | Reviewed |
| REQ-CL-004 | IF a column is not a NumPy array of its dtype and shape, the row counts differ, or there is no move, THEN `make_operation` SHALL raise `ValueError` naming the column. | unit: `test_a_column_of_the_wrong_type_is_refused`, `test_row_counts_must_agree`, `test_an_operation_without_moves_is_refused` | Reviewed |
| REQ-CL-005 | IF a `kind` or `role` value is not a member of its enum, a RAPID's role is not LINK, or a LINE's or ARC's role is LINK (research 26 subset: LINK for the rapids; LINE links come with D-087), THEN `make_operation` SHALL raise `ValueError`. | unit: `test_kinds_and_roles` | Reviewed |
| REQ-CL-006 | IF the first move is not a RAPID whose end is (NaN, NaN, z) with z finite, THEN `make_operation` SHALL raise `ValueError` (research 10, Method 1: the first move changes Z alone; trap 2). | unit: `test_the_first_move_is_a_rapid_along_the_axis` | Reviewed |
| REQ-CL-007 | IF a value of `end_mm` other than the first move's x and y is not finite, THEN `make_operation` SHALL raise `ValueError`. | unit: `test_an_end_that_is_not_finite_is_refused`; property: `test_a_value_that_is_not_finite_names_its_move` | Reviewed |
| REQ-CL-008 | IF the second move is a LINE or an ARC, THEN `make_operation` SHALL raise `ValueError` (ours: its start in the plane is not known). | unit: `test_the_second_move_is_not_a_line_or_an_arc` | Reviewed |
| REQ-CL-009 | IF a RAPID's feed class is not `NO_FEED_CLASS`, or a LINE's or ARC's is not an index of the header's feed classes, THEN `make_operation` SHALL raise `ValueError` (research 26, test 2: every LINE and ARC has a class, no RAPID has one). | unit: `test_feed_classes_by_kind` | Reviewed |
| REQ-CL-010 | IF a RAPID's link height is not finite, or a LINE's or ARC's is not NaN, THEN `make_operation` SHALL raise `ValueError` (research 10, Method 5). | unit: `test_link_heights_by_kind` | Reviewed |
| REQ-CL-011 | IF a RAPID ends below its link height, or a RAPID that changes x or y (move 1 always does) starts below it, THEN `make_operation` SHALL raise `ValueError` (D-062, D-087: G0 only at or above the link's height, and along the axis; research 26, test 5). The comparisons, and whether x or y changes, are exact (ours, DEC-CL-004). | unit: `test_the_profile_record_is_accepted`, `test_a_rapid_in_the_plane_below_its_link_height_is_refused`, `test_a_rapid_from_p_to_s_below_its_link_height_is_refused`, `test_the_rapid_up_from_p_one_ulp_off_counts_as_a_move_in_the_plane`, `test_move_1_counts_as_a_move_in_the_plane`; property: `test_a_rapid_ending_below_its_link_height_names_its_move` | Reviewed |
| REQ-CL-012 | IF move 0 or move 1 ends below the clearance height, or the last move is not a RAPID ending at or above it, THEN `make_operation` SHALL raise `ValueError` (D-062: the clearance height at the start and end of the operation; research 10, Method 1 and 4: the operation reaches its approach point at h_c). | unit: `test_a_diagonal_move_1_down_from_the_tool_change_is_refused`, `test_move_0_below_the_clearance_height_is_refused`, `test_the_operation_ends_with_a_rapid_at_the_clearance_height`, `test_the_profile_record_is_accepted`; property: `test_a_last_rapid_below_the_clearance_height_is_named` | Reviewed |
| REQ-CL-013 | IF a RAPID's or LINE's centre is not NaN or its sweep is not 0, THEN `make_operation` SHALL raise `ValueError`. | unit: `test_rapids_and_lines_have_no_centre_or_sweep` | Reviewed |
| REQ-CL-014 | IF an ARC's centre is not finite, or its sweep is not finite, is 0, or has a magnitude above 2π (the double nearest 2π, as geometry2d's), THEN `make_operation` SHALL raise `ValueError` (research 26 subset: \|sweep\| ≤ 2π). IF \|sweep\| equals 2π and the end is not the start bit for bit, or \|sweep\| is below 2π and the end lies within eps_len of the start, THEN it SHALL raise `ValueError` (research 26, Mapping: a full circle is the centre form with end = start; ours, DEC-CL-006: a tiny arc printed with end = start becomes a full circle on the control). | unit: `test_full_circles_with_end_at_start_pass`, `test_a_sweep_above_2pi_is_refused`, `test_a_full_circle_must_end_exactly_at_its_start`, `test_a_tiny_arc_is_refused`, `test_an_arc_needs_a_finite_centre_and_a_sweep`, `test_pinned_tiny_arc_at_eps_len` | Reviewed |
| REQ-CL-015 | IF an ARC's end z differs from its start z, THEN `make_operation` SHALL raise `ValueError` (research 26 subset: planar arcs, no helices; exact, DEC-CL-004). | unit: `test_an_arc_is_planar` | Reviewed |
| REQ-CL-016 | IF an ARC's radius at its start is not above eps_len, its end lies more than eps_len off its circle, or the angle from start to end in the sense of the sweep differs from \|sweep\| modulo 2π by more than eps_len / r, THEN `make_operation` SHALL raise `ValueError` naming the move (research 26, Arcs and test 1; the rules of geometry2d's REQ-G2D-042 and 043, decided the same on every platform, D-055). (AQ-006 (a).) | unit: `test_a_consistent_quarter_passes`, `test_an_end_off_the_circle_or_the_sweep_is_refused`, `test_a_ccw_quarter_given_a_cw_sweep_is_refused`, `test_an_arc_with_its_centre_at_its_start_is_refused`, `test_a_fillet_end_0_01_off_its_circle_is_refused`, `test_pinned_arcs_at_the_radial_boundary`; property: `test_valid_operations_pass_unchanged_and_read_only`, `test_an_arc_given_a_longer_sweep_names_its_move` | Reviewed |
| REQ-CL-017 | IF a header field is outside its range (name empty or not of ASCII letters, digits and underscores; a note line with a character below U+0020, U+007F or `"`; tool number or k below 1; a not finite or below 0; spindle speed, tol or a feed not finite or not above 0; a feed class name empty or repeated; clearance height not finite), THEN `make_operation` SHALL raise `ValueError` naming the field (research 26 subset; model REQ-MDL-012; the note's characters DEC-CL-005, provisional on RR-005). | unit: `test_a_header_field_out_of_range_is_refused` (23 cases, every field), `test_a_note_with_umlauts_and_signs_passes` | Reviewed |
| REQ-CL-018 | IF the work offset is below 1, there is no operation, or two operations have the same name, THEN `make_cl_data` SHALL raise `ValueError` (research 26, trap 13; DEC-MDL-005: NCXchange's messages are mapped back by the section); it SHALL rebuild every operation through `make_operation` and hold the rebuilt one. | unit: `test_the_work_offset_is_at_least_1`, `test_there_is_an_operation`, `test_operation_names_are_unique`, `test_an_operation_built_directly_is_checked_again`, `test_the_held_operation_is_the_rebuilt_one` | Reviewed |
| REQ-CL-019 | WHEN `make_operation` or `make_cl_data` returns, THE arrays of every `ClMoves` it holds SHALL be read-only copies, so a later change to the producer's arrays does not change the record (ours, as geometry2d's `curve_rows`). | unit: `test_make_operation_holds_read_only_copies`, `test_make_cl_data_holds_read_only_copies`; property: `test_valid_operations_pass_unchanged_and_read_only` | Reviewed |
| REQ-CL-020 | THE checks of an operation SHALL run in this order: REQ-CL-017, field by field in the order of `ClHeader`; then REQ-CL-004 to 016 by ID. `make_cl_data` SHALL check the work offset, then that there is an operation, then each operation in order as above, then repeated names. The `ValueError` SHALL name the operation, the first rule broken by its requirement ID and, for a move rule, the first move breaking it by its index from 0 (ours, DEC-CL-002, D-055). REQ-CL-016 thus sees only rows that passed REQ-CL-004 to 015. | unit: the message of every test above (`refusal` in `tests/support/cl_strategies.py`), `test_the_lower_requirement_is_named_first`, `test_the_first_breaking_move_is_named`, `test_a_broken_header_is_named_before_a_broken_move`; property: the four breakers in `tests/cl/property/test_make_operation_properties.py` | Reviewed |
| REQ-CL-021 | THE `make_operation` function SHALL decide the same on every platform: comparisons, `sqrt` and the arc rules of REQ-CL-016 only, no NumPy trigonometry in a decision (D-055 tier 1). (AQ-006 (a).) | review (spec-reviewer, this pull request); unit: `test_pinned_arcs_at_the_radial_boundary`, `test_pinned_tiny_arc_at_eps_len` | Reviewed |

## Invariants

- Every `ClOperation` that `make_operation` returns satisfies research 26 tests 1 (arcs), 2 (feeds) and 5 (rapids at or above their link height) for its moves, starts and ends at or above the clearance height, and holds only finite values outside the fill positions (REQ-CL-005 to 017). Property test: random valid operations pass; each one broken in one field raises naming that field.
- A returned record, from `make_operation` or `make_cl_data`, does not change: its arrays are read-only copies and its dataclasses frozen (REQ-CL-018, 019).

## Tolerance budget

None spent. eps_len is read for the tiny-arc rule (REQ-CL-014) and the arc rules (REQ-CL-016); every other comparison is exact (DEC-CL-004).

## Failure modes and diagnostics

No diagnostics: every rule broken is a producer's programming error and raises `ValueError` (DEC-CL-002). Expected outcomes, such as an empty region or a tool that does not fit, are the strategy's diagnostics before it builds a record.

## Algorithms and design inputs

No algorithms. The arc rules are geometry2d's (research 01, Curves; REQ-G2D-042, 043).

| Element | Public source, or own design with date |
| --- | --- |
| Header, move fields, roles, sweep sign | research 26, Structure and Arcs (D-052, D-057; ISO 14649 roles, SRC-113) |
| First move along the axis, link heights on rapids | research 10, Method 1 and 5 (D-062, D-087) |
| Columns of arrays, `ValueError` for broken records | ours, 2026-10-25 (DEC-CL-001, 002) |
| Name and note as the operation's comments | Project Spike `product/feature-map.md`, section 6 (Peter, 2026-10-07) |

## Example parts

- Research 22 test 1, the rectangle 100 × 60 with fillets R 5, tool D 10, stock top 0, three passes at −3.333…, −6.666… and −10: RAPID (NaN, NaN, 5) LINK, link height 5; RAPID to P at 5, link height 5; per pass RAPID Z 3, link height 3 (h_r), LINE Z z_i APPROACH plunge, LINE P → S APPROACH plunge, lines and CW arcs of radius 10 round the loop CUT cut, LINE S → P RETRACT cut, RAPID Z 5, link height 5. Accepted; the last move is the third pass's RAPID Z 5. Research 22 test 5's full circle (sweep −2π, end = start) is accepted too.
- The same with the second move a LINE: refused (REQ-CL-008). With a rapid from P to S at Z 3 and link height 5: refused (REQ-CL-011). With a fillet arc whose end is 0.01 mm off its circle: refused (REQ-CL-016).
- A note line "Rohteil 105 × 65": accepted here; NCXchange transliterates or warns `CMP022` for `×` (research 27, Comments row). A note line with a line break: refused (REQ-CL-017).

## Test plan

- Unit (`tests/cl/unit/`): one or more tests per requirement, tagged with its ID; the example parts.
- Property (`tests/cl/property/`): generated valid operations (random links, lines and consistent arcs at random levels) pass; each breaker of one field or one move raises naming its requirement (REQ-CL-020); arrays read-only.
- Golden cases: none (the record's serialisation is Later). Differential: none.

## Performance budget

`make_operation` on 100 000 moves under 50 ms on the reference machine (ours: vectorised checks; plan 0007 has about 50). Not checked by a test in this slice.

## Size estimate

First count about 205 NLOC of Python (types and enums 55, header checks 32, column and kind checks 45, link and height checks 32, arcs with full and tiny circles 28, `make_cl_data` 13); by Peter's rule of 2026-10-25 about 1.5 times that: **about 310 NLOC**, and about 450 lines of tests. Module budget 310 (AQ-007).

## Open questions

None. AQ-005 to AQ-008 answered 2026-10-26 (all as recommended): SPEC approved; `cl` depends on geometry2d through a public `check_arc_rows`; budget 310; the note is empty in plan 0007. RR-005 is answered in research 27, trap 15. Box 2 choices are in `src/splintercam/cl/DECISIONS.md`.

## Change log

- 2026-10-25: drafted for plan 0007, step 4, from research 26 and 10 and the feature map, section 6. Revised after the spec review the same day: the starts of moves 0 and 1 defined, move 1 at the clearance height (a diagonal from the tool change refused), full circles with end = start bit for bit, tiny arcs refused, reversed arcs a producer precondition, `make_cl_data` checks every operation again, the check order fixed, tol in the header for the writer's rounding allowance, k ≠ 1 left to the writer.
- 2026-10-26: Reviewed (Peter, AQ-005 to AQ-008 as recommended).

[r10]: ../../../docs/research/10-linking.md
[r26]: ../../../docs/research/26-toolpath-record.md
