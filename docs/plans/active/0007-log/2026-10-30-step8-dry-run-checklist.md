# 2026-10-30, step 8 (the dry-run checklist, from AQ-035)

- Peter's answer to AQ-035 (a): the slice writes no setup sheet; the setup notes stay in `testdata/zoo/profile-rectangle-fillets/README.md` ("Setup notes") and go into step 8's dry-run checklist, here. No program of the slice goes to an operator other than Peter until a setup sheet exists (its own plan, with these notes as its first requirements). `ncx` refuses a measurement point with a ≠ 0, as it refuses k ≠ 1, in its own pull request.
- Before the dry run: run the pinned `ncx check --strict` on `RECT_FILLETS.ncx` once (no test has yet; AQ-025), and run with the machine file of the job's name, so no `JOB_MACHINE_OVERRIDDEN` is reported (AQ-036 2 (b)).
- Checklist for `RECT_FILLETS` (1001) on the iTNC 530, from AQ-021, the profile's cnc review and the cnc review of `job` (pull request 91):
  1. T1 is the D 10 flat end mill, measured at its tip (axial offset 0). The NC program holds neither the diameter nor the measurement point; a wrong tool or a radius typed as the diameter cuts a wrong part with no message.
  2. The stock box is the real blank: (−5, −5, −20) to (105, 65, 0). A blank more than 1 mm (0.2·R) larger on the side of P is plunged into at the plunge feed.
  3. The approach point P is X 50, Y −11, 6 mm in front of the stock's front face (Y −5). The tool rapids to Z 3 there and feeds down to each pass, the last Z −10, at 300 mm/min. Nothing may stand there between Z 3 and Z −10 (in a vice, often inside the jaw's footprint).
  4. Clamps and jaws stay out of a band of 15 mm (t + 2R) round the part, down to Z −10.
  5. The first move after the tool change is a rapid along Z to the clearance height Z 5 at the tool-change position (research 10, trap 2): watch it.
  6. Three passes at Z −3.333, −6.667 and −10; clockwise round the part; a retract to Z 5 between passes.
  7. A witness mark on every pass at X 50 on the front face (Y 0), where S touches the wall.
  8. z_bottom −10 is above the stock bottom −20, so the part is not cut free; the stock margin of 5 mm is under s + 2R = 10 mm, so no pass is a full slot.
