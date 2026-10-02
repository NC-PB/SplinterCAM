---
paths:
  - "src/splintercam/**/kernel/**"
  - "CMakeLists.txt"
---

# Rules for C++ kernels

- A kernel takes NumPy arrays (nanobind `ndarray`) and plain values, and returns arrays, plain values and diagnostic codes. No Python objects, callbacks, OCCT or Qt types.
- Only `bindings.cpp` includes nanobind. Release the interpreter lock for any work longer than a few milliseconds; accept a cancellation flag and check it regularly.
- C++20 plus `std::expected`. No `new` or `delete`, no owning raw pointers, `std::span` for views. No exception leaves a kernel, except `std::bad_alloc` (out-of-memory is never swallowed; nanobind turns it into `MemoryError`).
- Include only libraries listed under `kernel_libraries` in `architecture/modules.yaml`.
- Warnings are errors; clang-tidy and the sanitizer build must stay clean. Never silence a warning or a sanitizer report without a comment giving the reason and a person's approval.
- Test through the module's Python API with property tests; add C++ unit tests only for internals the API cannot reach.
- Deterministic output: no output order from unordered containers, fixed merge order after parallel work.
