# SPDX-License-Identifier: Apache-2.0
"""Smoke tests of the build (plan 0001, step 1).

Infrastructure only: no requirement covers the build itself, so these tests carry no `req` marker.
"""

import importlib
import importlib.machinery
from pathlib import Path

import splintercam

SOURCE_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "splintercam"


def test_package_is_imported_from_the_source_tree() -> None:
    # The editable install must point at src/, or tests would run against a stale copy.
    assert Path(splintercam.__file__).resolve().parent == SOURCE_PACKAGE


def test_kernel_module_is_a_compiled_extension() -> None:
    kernels = importlib.import_module("splintercam._kernels")
    assert kernels.__file__ is not None
    assert kernels.__file__.endswith(tuple(importlib.machinery.EXTENSION_SUFFIXES))
    assert kernels.__doc__
