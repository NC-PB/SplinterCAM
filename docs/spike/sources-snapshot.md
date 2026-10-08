# Sources cited in this repository: snapshot of 2026-10-08

Public entries copied from Project Spike's source register (D-156); the register in project_spike is the master until the handover. Source PDFs are not in this repository.

### SRC-004 Vatti 1992: polygon clipping

- **Status:** processed
- **Class:** L
- **Type:** CACM 35(7), doi:10.1145/129902.129906
- **Read:** 2026-09-27, all pages; details in the literature note
- **Used for:** literature note in topic 02; point-sampling oracle for Booleans (A-053), per-edge tags (Q-037)
- **Rule:** distil into the topic (D-044).

### SRC-005 Held 1991: pocket machining, chapter 9 (direction-parallel milling mesh)

- **Status:** processed
- **Class:** L
- **Type:** Springer LNCS 500, doi:10.1007/3-540-54103-9; only Part III, chapter 9, pp. 127–137
- **Read:** 2026-09-27, all pages; details in the literature note
- **Used for:** literature note in topic 04; A-006 doubtful; Q-062
- **Rule:** distil into the topic (D-044).

### SRC-030 Held 1991: On the Computational Geometry of Pocket Machining (whole book)

- **Status:** processed
- **Class:** L
- **Type:** Springer LNCS 500, doi:10.1007/3-540-54103-9, 196 pages; chapter 9 already in SRC-005
- **Read:** 2026-09-28, chapters as listed in the notes
- **Used for:** literature notes in topics 02 (offsets defined by clearance), 03 (two: the Voronoi diagram of line and arc pockets; the full Voronoi route) and 04 (two: contour-parallel rules that do not depend on the offset method; what the direction-parallel chapters add); pointers in 04 and 10; A-004, A-005, A-006, A-053, A-054; Q-036, Q-037, Q-055, Q-058, Q-062, Q-063; new Q-076, Q-077. Chapter 9 is SRC-005
- **Rule:** distil into the topic (D-044).

### SRC-024 Piegl and Tiller 1997: The NURBS Book, 2nd edition

- **Status:** processed
- **Class:** L
- **Type:** Springer book, doi:10.1007/978-3-642-59223-2, 649 pages
- **Read:** 2026-09-27, chapters 2 to 7 and 12 in full (curves), 1 and 9 skimmed, surfaces skipped
- **Used for:** five literature notes in topic 01 (pointers in 11 and 21): curve representation for Q-035, proven flattening bound (ours), safeguarded projection; two misprints in the book noted
- **Rule:** distil into the topic (D-044).

### SRC-032 Shewchuk 1997: adaptive precision arithmetic and robust geometric predicates

- **Status:** processed
- **Class:** L
- **Type:** Discrete & Computational Geometry 18, doi:10.1007/PL00009321
- **Read:** 2026-09-28, all pages; details in the literature note
- **Used for:** literature note in topic 01 (exact predicates); pointer in 02; A-001; Q-033, Q-036; new Q-080
- **Rule:** distil into the topic (D-044).

### SRC-118 Plan 0001 prototype (test_repo) at commit c1c21d3: measurements and findings

- **Status:** processed
- **Class:** O
- **Type:** our own prototype: code, specs, measurements and CI results
- **Read:** 2026-10-01, the plan with its full progress log, both SPECs, the step 4 spike README, the commit history
- **Used for:** [prototype insights review]; Q-133; A-009, A-042; RK-005; T-019
- **Rule:** measurements are ours; cite the commit. The prototype reads the research snapshot of 2026-09-23, so its specs can lag project_spike (D-009).

### SRC-119 Altintas 2012: Manufacturing Automation, 2nd ed. (book)

- **Status:** processed
- **Class:** L
- **Type:** textbook, Cambridge University Press 2012, ISBN 978-1-107-00148-0, doi:10.1017/CBO9780511843723; 381 PDF pages
- **Read:** 2026-10-01, chapter 2 complete (pp. 4–65), section 3.3.3 (pp. 71–74), chapter 5 (pp. 191–249; 5.1 to 5.3 skimmed, 5.4 and 5.5 in full); formulas checked on page images. Not read: chapters 3 (rest), 4 (chatter), 6, 7 and later
- **Used for:** literature notes in topic 23 (cutting mechanics, power, tool life, wall error) and topic 11 (trajectory generation, interpolation); pointer note in 20; text fixes in 23 (A-050, A-051, η, radial force); cycle-time model steps 2, 5 and 6 in 11; A-062; citations in 01, 04, 10, 26 (trap 15, Sources) and 11 (Erkorkmaz eq. 51); Missing lines in 11, 23, 26, 27
- **Rule:** distil into the topics (D-044); copyrighted book, no tables or figures copied.

### SRC-122 Clipper2 2.0.1 source: sign tests

- **Status:** processed
- **Class:** O
- **Type:** open-source C++ library, the version pinned by D-135
- **Read:** 2026-10-02, `clipper.core.h` (`ProductsAreEqual`, `CrossProductSign`, `IsCollinear`, `CrossProduct`, `DotProduct`) and their call sites in `clipper.engine.cpp`, `clipper.offset.cpp` and `clipper.h`
- **Used for:** topic 01, resolution chain: Clipper2 decides most signs and collinearity with 128-bit integer products, but the spike test in `CleanCollinear` (`DotProduct`), `SegmentsIntersect` in `FixSelfIntersects`, the area thresholds in `DoSplitOp` and the input orientation of `ClipperOffset` decide in double (found by the review of 2026-10-02), so the kernel needs the 2^26 limit; A-001
- **Rule:** permissive licence; read to understand behaviour, no code copied.

### SRC-123 ezdxf documentation: the bulge value

- **Status:** processed
- **Class:** L
- **Type:** public documentation of ezdxf (MIT), the DXF library chosen in topic 21
- **Read:** 2026-10-02, the bulge definition and the bulge helper functions
- **Used for:** topic 01, section Curves (bulge definition and conversion)
- **Rule:** cite; the conversion formulas are ours.

### SRC-124 Welzl 1991: smallest enclosing disks

- **Status:** reference
- **Class:** L
- **Type:** paper
- **Read:** 2026-10-02, bibliographic record and abstract only (randomized, expected linear time)
- **Used for:** topic 01, Helpers (smallest enclosing circle for cylinder stock)
- **Rule:** read the paper before the enclosing-circle code is specified in detail.

### SRC-125 Wikipedia: Smallest-circle problem

- **Status:** processed
- **Class:** L
- **Type:** public encyclopedia article
- **Read:** 2026-10-02, the section on Welzl's algorithm (recursive definition, base cases, expected linear time, move-to-front remark) and its citation of Welzl 1991
- **Used for:** topic 01, Helpers (smallest enclosing circle)
- **Rule:** cite with SRC-124; confirm against the paper (topic 01 Missing list).

