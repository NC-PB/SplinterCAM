# 2026-10-31, step 8: the dry-run checklist (Project Spike session)

Steps 4 to 7 are on main (pull requests 85, 87, 89, 90, 91, 92, 93; 94 follows). CI builds the pinned `ncx` (pull request 88) and runs the golden case `testdata/zoo/profile-rectangle-fillets` end to end on Ubuntu: `ncx format --check`, `check --strict` and `compile` pass for the iTNC 530, the Fanuc 30i and the 840D sl files (main at 2b4c28a: 1927 passed, none skipped). The first such run found one real fault, `RPM` before `SPINDLE` in the tool block, fixed in pull request 92.

## The program

`splintercam run testdata/zoo/profile-rectangle-fillets/job.json --output <dir> --strict` with the pinned `ncx` writes `RECT_FILLETS.ncx` and `RECT_FILLETS.h` (1543 lines, iTNC 530 Klartext): `CYCL DEF 247` Q339 = 1, `TOOL CALL 1 Z S8000`, M3, M8; three passes at Z −3,333, −6,667, −10, each: `L X+50 Y-11 Z+5 FMAX`, down to Z+3 FMAX, F300 to the pass level beside the stock, F300 to S (X 50, Y −5), round the part clockwise (climb) at F1200 with the fillets as short lines, back to S and P, up to Z+5 FMAX; then M9, M5, M30.

## Before the dry run (setup)

1. T1 is the D 10 flat end mill, flute length 30, measured at its tip (axial offset 0). The program holds neither the diameter nor the measurement point (AQ-035, item 7): a wrong tool in pocket 1, or a length measured elsewhere, cuts a wrong part with no message.
2. Datum: work offset 1 (`CYCL DEF 247` Q339 = 1) at the drawing's origin, the part's lower left corner, Z 0 on the stock top. The part sits where it is drawn (100 × 60, fillets R 5).
3. The blank is the stock box: X −5 to 105, Y −5 to 65, Z −20 to 0. A blank more than 1 mm larger on the front side (Y below −5) is plunged into at F300 (AQ-035, item 3).
4. Nothing higher than Z+5 anywhere the tool rapids; clamps and jaws outside a band of 15 mm round the part down to Z −10 (AQ-015 item 1 (a), AQ-035 item 2). The part must be held from below or raised above the jaws: the profile cuts 5 mm outside the part all round.
5. At the approach point X 50, Y −11 (6 mm in front of the stock's front face) the tool goes from Z+3 down to Z −10: nothing may stand there; in a vice this is often inside the jaw's footprint (AQ-021, AQ-035 item 1).
6. No `BLK FORM` in the program (NCX has no stock word): set the blank by hand for the control's test-run graphics (AQ-010).

## During the dry run

7. After `TOOL CALL` the first move is `L Z+5 R0 FMAX` at the tool-change position, Z only; then across at Z+5 (AQ-015 item 3 (a)). Watch that this Z move is safe on your machine; if the iTNC moves differently after the tool change, that is a research request (research 10, trap 2).
8. Feeds: F300 down beside the stock and on the approach to S, F1200 round the part, FMAX only at Z+3 and above.
9. The fillets are many short `L` blocks (no `CC`/`C`): watch whether the control slows there (D-023, arc fitting later).
10. The witness mark at S (X 50, Y 0 on the front face) on every pass is expected (AQ-016 item 7).
11. Program end: M9, M5, M30 at Z+5 over P (AQ-010 item 2).

## After

12. Findings go back as decisions or research requests (plan 0007, step 8). Only Peter runs programs of the slice until a setup sheet exists (AQ-035).
