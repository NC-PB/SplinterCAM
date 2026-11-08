# 2026-11-08, step 8: the offline check in place of the dry run (Project Spike session)

Peter has no machine or simulator at hand (2026-11-08); step 8 stays open for a machine test or the community. This is what was checked without one, on `main` at d9b729b, with the pinned `ncx` (f74559c) built on the Mac.

Program: `splintercam run testdata/zoo/profile-rectangle-fillets/job.json --output <dir> --strict` against `heidenhain-itnc530.toml`: exit 0, `RECT_FILLETS.ncx` and `RECT_FILLETS.h` (1543 lines).

## NCXchange's virtual machine

- `ncx trace --strict`: exit 0, 3049 state changes. The sequence is as planned: `UNITS=MM`, `ORIGIN` 0 to 1, `TOOL:H1` 1 with `OFFSET:LEN:H1` 1, spindle CW at 8000, coolant on; Z 5 from the machine position, X 50 Y −11 at Z 5, Z 3, then F300 to Z −3,333333, F300 to Y −5,0008, F1200 round the part; the same for the passes at −6,666667 and −10; coolant and spindle off at the end.
- `ncx analyze --strict`: exit 0. One tool, T1 at 8000 1/min, feeds 300 to 1200 mm/min; cutting 1093,8 mm (three loops of 342,8 mm, the radius 10 arcs about the fillet centres, plus the descents and the approach and retract lines: 1093,5 mm by hand), rapid 41 mm, 2 motions of unknown length (the first Z move from the unknown tool-change position, and the move after it); estimated 65 s on the machine file's dynamics (an estimate, not a measured time).

## Geometry against the part

The cut moves were parsed from `RECT_FILLETS.ncx` and each segment sampled against the part, the rectangle 100 × 60 with R 5 fillets (Project Spike session, a script outside the repository):

- closest approach of any cut segment to the part: 5,0007 mm for the tool radius 5: no gouge, 0,7 µm on the air side;
- largest distance of the contour pass: about 5,001 mm, inside tol 0,01;
- no rapid moves in the plane below Z 5, and no rapid ends below Z 3;
- direction: clockwise round the part (climb with M3).

What this does not check, and only a machine or a simulator can: how the iTNC moves Z after `TOOL CALL` (research 10, trap 2), the control's smoothing through the many short blocks of the fillets, the real tool and its measured length, clamps and the blank.
