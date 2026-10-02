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
| tolerance set | `ToleranceSet` | Toleranzsatz | All tolerances of an operation and their shares per stage | 01 |
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
