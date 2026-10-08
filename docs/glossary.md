# Glossary

<!-- Domain terms and the exact names to use for them in code (Python: snake_case for functions and variables,
     PascalCase for classes; the same words in C++). Agents: use the "Code name" column,
     never a synonym. Add a term in the same change that introduces it. German column: draft, to be checked. -->

| Term | Code name | German (draft) | Meaning | Research |
| --- | --- | --- | --- | --- |
| allowance | `allowance` | Aufmass | Material deliberately left for a later operation; negative to cut beyond the model (D-150) | 04, 07 |
| stepover (ae) | `stepover` | seitliche Zustellung | Radial distance between neighbouring passes | 04, 23 |
| stepdown (ap) | `stepdown` | Zustelltiefe | Axial depth per pass or level | 07, 23 |
| engagement angle | `engagement_angle` | Eingriffswinkel | Angle over which the tool is in contact with material | 05 |
| chip thickness (hex, hm) | `max_chip_thickness`, `mean_chip_thickness` | Spandicke | Maximum and average uncut chip thickness | 05, 23 |
| stock | `stock` | Rohteil | The material before and during machining; the stock model tracks what remains | 08 |
| rest material | `rest_material` | Restmaterial | Material a previous tool could not reach | 08 |
| material wall / air boundary | `material_wall`, `air_boundary` | Materialwand / offene Kante | Boundary the tool must not cross / boundary it may cross | 04 |
| island | `island` | Insel | Material inside a pocket that must stay | 04 |
| pass | `cut_pass` (`pass` is reserved in Python) | Bahn | One continuous cutting sequence | 04, 10 |
| link | `link` | Verbindungsbewegung | Move between two passes | 10 |
| lead-in, lead-out | `lead_in`, `lead_out` | Anfahr-, Abfahrbewegung | Tangential approach to and departure from a cut | 10 |
| retract | `retract` | Rückzug | Move away from the material, along the tool axis first | 10 |
| rapid | `rapid` | Eilgang | Positioning move at maximum speed (G0) | 10 |
| clearance, retract and feed height | `clearance_height`, `retract_height`, `feed_height` | Sicherheits-, Rückzugs-, Vorschubhöhe | The three safe heights of an operation | 10 |
| chord tolerance | `chord_tolerance` | Sehnentoleranz | Maximum deviation of a flattened or fitted curve | 01, 11 |
| tolerance set | `ToleranceSet` | Toleranzsatz | All tolerances of an operation: epsilons, tol and its budget parts | 01 |
| budget part | `BUDGET_PARTS`: `geometry`, `fit`, `control`, `reserve` | Toleranzanteil | A part of the operation tolerance tol, with its base share (D-056, D-146) | 01 |
| grid unit (u) | `grid_unit_mm` | Rasterweite | Step of the offset kernel's integer grid, 0.0001 mm (D-058, D-132) | 01, 02 |
| flattening tolerance (t_flat) | `flatten_tol_mm` | Sehnentoleranz der Diskretisierung | What the geometry part leaves for flattening curves (REQ-FND-009) | 01 |
| topology tolerance (t_topo) | `topology_tol_mm` | Topologietoleranz | Features closer than this count as touching in the float stages, 2u | 01 |
| declared parameter | `DeclaredParameter` | deklarierter Parameter | A value with its unit, default, range and source (D-049) | 01 |
| line | `Line` | Strecke | A straight curve from P0 to P1 (D-057) | 01 |
| arc | `Arc` | Kreisbogen | A circular curve in centre form: exact end points, centre, signed sweep (D-057) | 01 |
| sweep | `sweep_rad` | Öffnungswinkel | Signed angle of an arc, positive counter-clockwise, 0 < \|sweep\| ≤ 2π | 01 |
| exact predicate | `orient2d`, `incircle`, `in_arc_circle` | exaktes Prädikat | A sign test whose sign is exact for the given doubles: side, collinearity, inside a circle (D-097) | 01 |
| air side | `AirSide` (`LEFT`, `RIGHT`) | Luftseite | Where air lies beside a curve, seen along it; a flattened arc keeps its error there (research 01, Flattening) | 01 |
| bounding box | `Box` | Begrenzungsrechteck | Axis-aligned box of a curve, in mm | 01 |
| bulge | `bulge` | Bulge (Ausbauchung) | DXF polyline value of an arc: tan(φ/4), positive counter-clockwise, only at DXF import and export (D-057) | 01 |
| closest point | `ClosestPoint` | nächster Punkt | The point of a curve nearest to a query point, with its parameter and distance (research 01, Distances) | 01 |
| signed area | `signed_area` | vorzeichenbehaftete Fläche | Area of a loop, positive for a counter-clockwise loop (research 01, Area and orientation) | 01 |
| point location | `PointLocation` (`IN`, `OUT`, `ON`) | Punktlage | Where a point lies against a region: ON within eps_len of the boundary, else IN where the winding number is not 0 (research 01, Point in region) | 01 |
| zero-width spike | `CLEANUP_SPIKE` | Nullbreiten-Spitze | A vertex where a loop turns back exactly onto itself; cleanup drops it without changing the region (research 01, Helpers) | 01 |
| zero-width slit | `LOOP_SLIT`, `split_slits` | Nullbreiten-Schlitz | A run of rows a loop runs out and back exactly, with rows on both sides, as a keyhole drawn as one loop; the loop tree removes it and splits the loop in two (REQ-G2D-241) | 01 |
| curve rows | `CurveRows` | Kurvenzeilen | Lines and arcs of closed loops as arrays at the kernel boundary: [x0, y0, x1, y1, cx, cy, sweep] per row, IDs, loop starts | 01 |
| loop tree | `loop_tree`, `LoopTree` | Konturbaum | Closed loops checked and nested: degenerate, duplicate and crossing loops reported, parents and depths found, even depth CCW and odd depth CW (research 01, Loop tree) | 01 |
| topology flattening | (inside `loop_tree`) | Topologie-Diskretisierung | Arcs replaced by polylines within u, for the loop tree's decisions only (research 01, Loop tree, rule 1) | 01 |
| side-correct flattening | `flatten_loops` | seitenrichtige Diskretisierung | Flattening of a region's loops within t_flat with every arc's error in air (research 01, Flattening) | 01 |
| region kind | `RegionKind` (`MATERIAL`, `AIR`) | Bereichsart | What fills the region a set of loops bounds; it decides the air side of each arc. Not the edge classes of D-059 | 01 |
| polygon region | `PolygonRegion` | Polygonbereich | A region as flat loops at the kernel boundary: points, loop starts, a source ID and a fixed-node flag per vertex; outer loops CCW, holes CW | 01, 02 |
| machining region | `build_region`, `FlatRegion` | Bearbeitungsbereich | The region an operation works in: the Clipper2 PolyTree of the side-correct flattened loops, with the extra clearance its offsets must add | 01, 02 |
| fixed node | `fixed` | Fixpunkt | A vertex that later steps must not move or merge, such as a pinch point (D-084) | 01, 02 |
| scallop height | `scallop_height` | Kammhöhe | Height of the ridge left between passes | 09 |
| toolpath | `Toolpath` | Werkzeugweg | Ordered passes and links of one operation | 10 |
| CL data | `ClData` | CL-Daten | Neutral cutter-location output before the post | 13 |
| driven point | `driven_point` | Führungspunkt | The tool point a path is programmed for | 19 |
| work frame | `work_frame` | Werkstücknullpunkt | Coordinate frame the program refers to (G54 and similar) | 19 |
| setup | `Setup` | Aufspannung | One clamping of the part, with stock, fixtures and origin | 19 |
| fixture | `fixture` | Spannmittel | Clamping device; a keep-out zone | 10, 19 |
| insert | `insert` | Wendeschneidplatte | Replaceable cutting tip of a turning or milling tool | 14 |
| nose radius | `nose_radius` | Eckenradius | Corner radius of a turning insert | 14 |
| entering angle (κr) | `entering_angle` | Einstellwinkel | Angle between the main cutting edge and the feed direction | 14, 23 |
| medial axis | `medial_axis` | Mittelachse | Skeleton of a region; centres of largest inscribed circles | 03 |
| drop-cutter | `drop_cutter` | (kein gängiger Begriff) | Lowest tool tip height at a point without touching the part | 06 |
| waterline | `waterline` | Wasserlinie | Level curve of the tool against the part at a given height | 07 |
| canned cycle | `canned_cycle` | Bearbeitungszyklus | Control cycle such as G81 or G71 | 13, 16, 20 |
| post-processor | `PostProcessor` | Postprozessor | Turns CL data into a control's program | 13 |
| boundary | `boundary` | Begrenzung | Region that limits where an operation cuts; the tool is inside, centred on or outside it | 25 |
| machining faces | `machining_faces` | Bearbeitungsflächen | Faces an operation machines | 25 |
| check faces | `check_faces` | Kontrollflächen | Faces the tool must avoid, with their own allowance | 25 |
| selection slot | `SelectionSlot` | Auswahlfeld | Declared geometry input of a strategy: entity types, count, required | 25, dev/11 |
| diagnostic | `Diagnostic` | Meldung | Typed result message of an operation (code, severity, location) | dev/03 |
