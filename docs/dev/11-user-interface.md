[Index](README.md) · [← 10. Stack decision](10-stack-decision.md) · [12. Lean code →](12-lean-code.md)

# 11. User interface

The desktop application ([ADR 0004](../decisions/0004-tech-stack.md): PySide6 with Qt Widgets and the OCCT viewer) is a client of the `job` module ([ADR 0007](../decisions/0007-headless-first.md)). This document fixes the layout, the interaction model and the rules that keep the interface small in code: most of it is generated from declarations, so adding a strategy needs no interface code. The geometry behind every selection is in [research 25](../research/25-machining-areas-and-selections.md).

## Principles

1. **No computation in the GUI.** Every action is a call to the `job` API that the command-line runner can make too. The GUI shows state and sends commands.
2. **Generated, not hand-built.** Operation panels are generated from each strategy's parameter declarations and selection slots ([research 19](../research/19-software-design.md#operations)). A new strategy gets its panel for free.
3. **Show the consequence.** Boundaries, tool positions, start points, leads and the stock are previewed in the 3D view while the user edits, computed by the same code that computes the toolpath.
4. **Nothing silent.** Every warning and error is a diagnostic with a link to the operation, the parameter and the geometry it concerns.
5. **Never block.** Computations run in the background with progress and a cancel button; the window always responds.

## Main window

```text
+----------------------------------------------------------------------------+
| Menu and toolbar: file, setup, operations, simulate, post                  |
+------------------+--------------------------------------+------------------+
| Job tree         |                                      | Properties       |
|  Setup 1         |                                      |  (generated for  |
|   Machine        |             3D view                  |   the selected   |
|   Work frame     |   OCCT viewer: hover, selection,     |   item)          |
|   Part           |   previews, toolpaths, stock         |                  |
|   Stock          |                                      |                  |
|   Fixtures       |                                      |                  |
|   Operations     |                                      |                  |
|    1 Facing      |                                      |                  |
|    2 Adaptive  ! |                                      |                  |
|    3 Drilling    |                                      |                  |
|  NC programs     |                                      |                  |
+------------------+--------------------------------------+------------------+
| Bottom dock: Diagnostics | Tools | Log                                     |
+----------------------------------------------------------------------------+
| Status bar: selection filter, units, active work frame, progress, cancel   |
+----------------------------------------------------------------------------+
```

- **Job tree:** setups with their machine, work frame, part, stock and fixtures; operations in machining order with a status icon (valid, needs recompute, computing, error, broken selection); NC programs. Context actions: compute, duplicate, suppress, reorder by dragging, create transformed copies (rotate, mirror, pattern).
- **Properties:** the generated panel of whatever is selected in the tree.
- **Bottom dock:** diagnostics of all operations, the tool library, and the log.
- All docks can be moved and closed; the layout is saved per user.

## Operation panels

Parameters appear in the same groups, in the same order, for every strategy; groups without parameters are hidden.

| # | Group | Contents |
| --- | --- | --- |
| 1 | Tool and cutting data | Tool, driven point, spindle speed and feeds from the cutting-data solver, with a lock per value ([research 23](../research/23-cutting-data.md)) |
| 2 | Geometry | The selection slots of the strategy: machining faces, check faces, boundaries, curves, points, stock source |
| 3 | Area | Tool position against boundaries, height limits, slope limits, rest material |
| 4 | Strategy | Pattern, stepover, stepdown, direction, allowances, tolerance |
| 5 | Order | Levels or regions, one-way or zigzag, start point, reverse |
| 6 | Entry, leads and links | Entry type, lead-in and lead-out, link types with their fallbacks, the three safe heights |
| 7 | Tool axis | Multi-axis strategies only ([research 12](../research/12-multi-axis-kinematics.md)) |
| 8 | Collision | Tool parts to check, clearances, what to do on a collision |
| 9 | Feeds by move type | Cutting, plunge, ramp, lead, link and rapid; feed control options ([research 11](../research/11-path-optimisation.md)) |
| 10 | Output | Arc fitting, tolerance shares, the controller's smoothing mode, comments |

A **basic view** shows the parameters marked as basic (typically ten or fewer); the **advanced view** shows all. Both edit the same values.

To generate this, each parameter declaration carries, besides type, unit and default: its group, a basic or advanced flag, a label, a tooltip, a link to the help text, an allowed range, and an optional visibility condition in a small expression language (for example "only for closed contours"). A test checks that every declared parameter has all of these ([06](06-testing-and-quality-gates.md)).

Numeric fields accept units and expressions ("10 mm", "0.4 * tool.diameter"), stored in millimetres ([research 19](../research/19-software-design.md#units-and-expressions)).

## Selection slots

Each strategy declares its selection slots: a name, the allowed entity types (faces, edges, curves, points, solids), the minimum and maximum count, and whether it is required. In the Geometry group each slot shows its count and state: complete, required but empty, or broken.

- **Picking.** Clicking a slot puts the 3D view into picking mode with a selection filter for exactly the allowed types. Hovering highlights candidates; a click adds, a second click on a picked item removes it; Escape ends picking. Box selection adds all candidates inside the rectangle.
- **Face helpers.** Add tangent-connected faces; add faces by type (all horizontal planes, all cylinders of a diameter); add faces by slope range.
- **Curve chaining.** Picking one edge proposes the whole tangent-continuous chain; at a fork the candidates are highlighted and the user picks the branch. An arrow shows the direction (click to flip) and a marker shows the side.
- **Points.** Picked on geometry with snapping (vertex, edge midpoint, arc centre, point on a face) or typed as coordinates in the work frame.
- **Previews.** The region the tool centre may use (translucent fill), the tool outline at the start point, lead-in arcs, the stock box, the face orientation (two-coloured shading).
- **Broken selections** (the part changed and a reference could not be re-mapped, [research 25](../research/25-machining-areas-and-selections.md#storing-selections)) are shown in red with a "pick again" action; the operation stays invalid until they are fixed.

## 3D view

- Rotate, pan and zoom; view cube; standard views; fit all; section planes.
- Display modes: shaded, wireframe, transparent stock.
- Toolpath display filtered by operation and coloured by move type (rapid, feed, link, lead, plunge), with the tool shown at a chosen position.
- Selection and previews as above; the work frame is always shown as a small triad.

## Simulation workspace

A separate workspace, reached from the toolbar:

- **Transport:** play, pause, step by move, step by operation, speed; a timeline over the whole program.
- **Move list** synchronised with the view: selecting a line moves the tool there, and the current NC block is highlighted.
- **Stock analysis:** the simulated stock coloured by its deviation from the part (gouges in one colour, material above the allowance in another), with a measuring tool for distances and remaining thickness.
- **Toolpath analysis:** colouring by feed, move type, operation or engagement.
- **Machine:** axis positions against their limits, and manual jogging of each axis to check limits and collisions.
- **Statistics:** times per operation (feed and rapid), distances, tool changes.
- **Events:** collisions, limit violations and air cuts as a list; clicking an event jumps to its position.

## Diagnostics

The diagnostics dock lists the typed diagnostics of all operations ([03](03-architecture-rules.md)), filterable by severity and operation. Selecting one selects the operation, highlights the parameter and shows the geometry it refers to.

## Long computations

Operations compute in worker processes. The tree shows progress per operation and the status bar the overall progress with a cancel button. Editing a parameter marks only the affected aspects dirty ([research 19](../research/19-software-design.md#operations)) and recomputes in the background.

## Testing the interface

- A declaration test: every parameter and selection slot has the fields listed above.
- View models (tree model, generated panels, selection controller) are tested without a window.
- A small set of GUI smoke tests drives the real window (for example with pytest-qt): open a part, pick a face, compute, simulate.
- Screenshots of the 3D view for a few reference cases are compared by eye in pull requests, not pixel by pixel.

## Not in the first versions

Ribbon interface, custom themes, touch input, a node-based process editor.

---

[Index](README.md) · [← 10. Stack decision](10-stack-decision.md) · [12. Lean code →](12-lean-code.md)
