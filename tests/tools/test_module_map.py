# SPDX-License-Identifier: Apache-2.0
"""Tests of the reader of architecture/modules.yaml used by tools/arch-check (plan 0006).

Infrastructure only: no requirement covers the tools, so these tests carry no `req` marker.
"""

import pytest

from module_map import MapError, module_map, parse, read_module_map
from runner import ROOT


def test_the_repository_map_is_read_in_full() -> None:
    map_ = read_module_map(ROOT / "architecture" / "modules.yaml")
    geometry2d = map_.modules["geometry2d"]
    assert (geometry2d.layer, geometry2d.kernel) == (1, True)
    assert geometry2d.kernel_interface == ("exact.hpp", "distance.hpp", "grid.hpp")
    assert map_.modules["offset2d"].kernel_includes == ("geometry2d",)
    assert map_.external["OCP"] == ("io", "features", "apps/desktop")
    assert map_.libraries["nanobind"] == ("*",)
    assert "no-cycles" in map_.rules
    assert "strategies/pocket" in map_.matching(["strategies/*"])


def test_the_subset_block_inline_comments_and_scalars() -> None:
    text = """
# a comment line
top:
  name: { layer: 2, flag: true, off: false, list: [a, "b # not a comment", c/d] }  # trailing
  plain: public domain
items:
  - first
  - "second"
version: 2
"""
    assert parse(text) == {
        "top": {
            "name": {
                "layer": 2,
                "flag": True,
                "off": False,
                "list": ["a", "b # not a comment", "c/d"],
            },
            "plain": "public domain",
        },
        "items": ["first", "second"],
        "version": 2,
    }


@pytest.mark.parametrize(
    "text",
    [
        "a: &anchor 1\n",
        "a:\n  - x\n  y: 1\n",
        "a: 1\n    b: 2\n",
        'a: "open\n',
        "a: [x, y\n",
        "a:\n",
        "a:b\n",
        "a: { k: v } extra\n",
        "a: 1\na: 2\n",
    ],
)
def test_text_outside_the_subset_is_refused(text: str) -> None:
    with pytest.raises(MapError):
        parse(text)


@pytest.mark.parametrize(
    "entry",
    [
        "{ kernel: false, depends_on: [] }",
        "{ layer: x, kernel: false }",
        "{ layer: 1, kernel: maybe }",
        "{ layer: 1, kernel: false, depends_on: core }",
    ],
)
def test_a_module_entry_without_its_fields_is_refused(entry: str) -> None:
    with pytest.raises(MapError, match="module m"):
        module_map(parse(f"modules:\n  m: {entry}\n"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("- a\n", "modules.yaml: expected a mapping"),
        ("modules: [a]\n", "modules: expected a mapping"),
        ("kernel_libraries:\n  x: { used_by: all }\n", "library x: used_by must be a list"),
        ("external:\n  x: [a]\n", "external x: expected a mapping"),
        ("external:\n  x: { allowed_in: io }\n", "external x: allowed_in must be a list"),
        ("rules: none\n", "modules.yaml: rules must be a list"),
    ],
)
def test_a_map_of_the_wrong_shape_is_refused(text: str, expected: str) -> None:
    with pytest.raises(MapError, match=expected):
        module_map(parse(text))
