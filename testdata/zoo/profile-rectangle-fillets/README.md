<!-- SPDX-License-Identifier: Apache-2.0 -->

# profile-rectangle-fillets

Plan 0007's first NC program (`src/splintercam/job/SPEC.md`, REQ-JOB-023): research 22 test 1,
an outside profile of research 21 test 1's drawing.

- `part.dxf`: a rectangle 100 × 60 mm from (0, 0) with four fillets of radius 5, one closed
  LWPOLYLINE with bulges, `$INSUNITS` 4 (millimetres). Written by `make_part.py` with ezdxf.
- `job.json`: the job of the model SPEC's Example parts (`src/splintercam/model/SPEC.md`): T1, a
  flat end mill D 10 with 30 mm of flute at the tip; the stock from (−5, −5, −20) to (105, 65, 0);
  work offset 1; `PROFILE_1`, 8000 1/min, tol 0.01, z 0 to −10, step-down 4, feeds 1200 and 300;
  program `RECT_FILLETS` 1001 for the Heidenhain iTNC 530.
- `case.json`: the checks, as data (docs/dev/06), run by `tests/job/golden/`: three passes, the
  sides offset by 5, the fillets in the band of radius 10, clockwise, the start in the middle of a
  long side, the approach point 6 mm clear of the stock; with the real `ncx`, `check --strict`
  passes and `compile` writes `RECT_FILLETS.h`.
- `expected/`: not yet; a person adds it with `tools/golden-approve` (AQ-011 item 5).

## Setup notes

`job` writes no setup sheet yet (`src/splintercam/job/SPEC.md`, Scope, Later; AQ-035). Until it
does, the notes for this case's setup and for Peter's dry run (plan 0007, step 8), from AQ-021 and
the profile's cnc review (`docs/plans/active/0007-log/`):

1. The approach point P lies R + 0.2·R = 6 mm beside the stock on the side of the start point S:
   X 50, Y −11, in front of the stock's front face (Y −5). The tool rapids to Z 3 there and feeds
   down to each pass level, the last Z −10, at 300 mm/min. Nothing may stand there between Z 3 and
   Z −10; in a vice this is often inside the jaw's footprint.
2. Clamps and jaws stay out of a band of t + 2R = 15 mm round the part, down to Z −10.
3. A blank more than 1 mm (0.2·R) larger than the stock box on the side of P is plunged into at
   the plunge feed: the stock box must be the real blank.
4. A z_bottom equal to the stock bottom would cut the part free (here −10 against −20: not).
5. Where the stock margin exceeds s + 2R = 10 mm, every pass is a full slot (here 5 mm: not).
6. A witness mark on every pass where S touches the wall: X 50 on the front face, Y 0 (S
   itself, X 50, Y −5, is the tool centre).
7. The NC program holds neither the tool's diameter nor its measurement point: T1 must be the
   D 10 flat end mill, measured at its tip (axial offset 0), or the part is wrong with no message.
8. Dry run: the first move after the tool change is a rapid along Z to the clearance height Z 5
   at the tool-change position (research 10, trap 2).

The machine file is not in this folder: it comes from the pinned NCXchange checkout named by
`SPLINTERCAM_NCXCHANGE` (DEC-JOB-004). Run as it is, the job stops with `JOB_MACHINE_NOT_FOUND`.

Source: drawn for this project. Licence: Apache-2.0 (`testdata/LICENSES.md`).
