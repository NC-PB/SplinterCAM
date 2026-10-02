---
paths:
  - "src/splintercam/io/**"
  - "src/splintercam/features/**"
  - "src/splintercam/apps/desktop/**"
---

# Rules for code that uses OCCT through OCP

- OCP is allowed only in `io`, `features` and `apps/desktop`. No other module imports `OCP`.
- OCCT objects never leave these modules. Between modules a shape travels as a `ShapeRef` (serialised B-rep plus its stable face and edge IDs); meshes and curves travel as NumPy arrays.
- Stable IDs come from one indexed map of sub-shapes, built once per `ShapeRef`. Never use Python object identity or hashes of OCCT objects as IDs.
- Treat OCCT as not thread-safe: call it from one thread per process. Long operations (large STEP imports, sewing, tessellating big models) run in a worker process.
- Wrap OCP calls in small typed functions; `Any` from OCP never appears in a public signature.
- Check every OCCT result (`IsDone()`, status values) and turn failures into diagnostics.
- Viewer code: all AIS calls on the GUI thread; pack toolpaths into a few large arrays, never one object per move.
