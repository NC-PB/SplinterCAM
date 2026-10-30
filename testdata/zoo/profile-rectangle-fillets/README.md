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

The machine file is not in this folder: it comes from the pinned NCXchange checkout named by
`SPLINTERCAM_NCXCHANGE` (DEC-JOB-004). Run as it is, the job stops with `JOB_MACHINE_NOT_FOUND`.

Source: drawn for this project. Licence: Apache-2.0 (`testdata/LICENSES.md`).
