# SPDX-License-Identifier: Apache-2.0
"""architecture/modules.yaml read in full, for tools/arch-check (plan 0006).

The standard library has no YAML reader and no package is added for one (Peter, 2026-10-08), so
this reads the subset the file uses: block mappings and lists by indentation, inline mappings and
lists, comments, quoted and plain scalars, integers and booleans. Anything else is a MapError.
"""

import fnmatch
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

type Node = str | int | bool | list[Node] | dict[str, Node]

_INTEGER = re.compile(r"-?\d+")
_FLOW_STOP = ",]}"


class MapError(Exception):
    """modules.yaml is not in the subset this reader knows, or an entry lacks a field."""


@dataclass(frozen=True, slots=True)
class Module:
    name: str
    layer: int
    kernel: bool
    depends_on: tuple[str, ...]
    kernel_includes: tuple[str, ...]
    kernel_interface: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModuleMap:
    modules: dict[str, Module]
    rules: tuple[str, ...]
    # Library name -> the modules whose kernels may include it ("*" for all).
    libraries: dict[str, tuple[str, ...]]
    # Python import name -> the modules allowed to import it ("*" for all).
    external: dict[str, tuple[str, ...]]

    def matching(self, patterns: Iterable[str]) -> list[str]:
        """The declared modules a list of names or patterns ("strategies/*") stands for."""
        return sorted({m for p in patterns for m in self.modules if fnmatch.fnmatchcase(m, p)})


def _strip_comment(line: str) -> str:
    quoted = False
    for i, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == "#" and not quoted and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line.rstrip()


def _plain(text: str) -> Node:
    text = text.strip()
    if text in ("true", "false"):
        return text == "true"
    if _INTEGER.fullmatch(text):
        return int(text)
    if not text or text[0] in "&*!|>'%@`{[":
        raise MapError(f"unsupported value {text!r}")
    return text


class _Flow:
    """An inline value: {key: value, …}, [value, …], "quoted" or plain."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.at = 0

    def _skip(self) -> None:
        while self.at < len(self.text) and self.text[self.at] == " ":
            self.at += 1

    def _expect(self, char: str) -> None:
        self._skip()
        if self.text[self.at : self.at + 1] != char:
            raise MapError(f"expected {char!r} at {self.at} in {self.text!r}")
        self.at += 1

    def _items[T](self, close: str, item: Callable[[], T]) -> list[T]:
        items: list[T] = []
        self._skip()
        while self.text[self.at : self.at + 1] != close:
            items.append(item())
            self._skip()
            if self.text[self.at : self.at + 1] == ",":
                self.at += 1
                self._skip()
        self.at += 1
        return items

    def value(self, stop: str = _FLOW_STOP) -> Node:
        self._skip()
        char = self.text[self.at : self.at + 1]
        if char == "{":
            self.at += 1
            return dict(self._items("}", self._pair))
        if char == "[":
            self.at += 1
            return self._items("]", self.value)
        if char == '"':
            end = self.text.find('"', self.at + 1)
            if end < 0:
                raise MapError(f"unterminated quote in {self.text!r}")
            value, self.at = self.text[self.at + 1 : end], end + 1
            return value
        start = self.at
        while self.at < len(self.text) and self.text[self.at] not in stop:
            self.at += 1
        return _plain(self.text[start : self.at])

    def _pair(self) -> tuple[str, Node]:
        key = self.value(":" + _FLOW_STOP)
        self._expect(":")
        return str(key), self.value()

    def whole(self) -> Node:
        value = self.value("")
        self._skip()
        if self.at != len(self.text):
            raise MapError(f"trailing text in {self.text!r}")
        return value


def _block(lines: Sequence[tuple[int, str]], start: int, indent: int) -> tuple[Node, int]:
    """The block of lines from `start` indented by exactly `indent`, and the line after it."""
    is_list = lines[start][1].startswith("- ")
    items: list[Node] = []
    pairs: dict[str, Node] = {}
    at = start
    while at < len(lines) and lines[at][0] == indent:
        text = lines[at][1]
        if is_list != text.startswith("- "):
            raise MapError(f"a list and a mapping mixed at {text!r}")
        at += 1
        if is_list:
            items.append(_Flow(text[2:]).whole())
            continue
        key, colon, rest = text.partition(":")
        if key in pairs:
            raise MapError(f"{key!r} appears twice")
        if not colon or (rest and not rest.startswith(" ")):
            raise MapError(f"expected 'key: value' in {text!r}")
        if rest.strip():
            pairs[key] = _Flow(rest.strip()).whole()
        elif at < len(lines) and lines[at][0] > indent:
            pairs[key], at = _block(lines, at, lines[at][0])
        else:
            raise MapError(f"{key!r} has no value")
    if at < len(lines) and lines[at][0] > indent:
        raise MapError(f"unexpected indentation at {lines[at][1]!r}")
    return (items if is_list else pairs), at


def parse(text: str) -> Node:
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if line.strip():
            lines.append((len(line) - len(line.lstrip(" ")), line.strip()))
    if not lines:
        return {}
    node, at = _block(lines, 0, lines[0][0])
    if at != len(lines):
        raise MapError(f"unexpected indentation at {lines[at][1]!r}")
    return node


def _mapping(node: Node, where: str) -> dict[str, Node]:
    if not isinstance(node, dict):
        raise MapError(f"{where}: expected a mapping")
    return node


def _names(entry: dict[str, Node], key: str, where: str) -> tuple[str, ...]:
    value = entry.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise MapError(f"{where}: {key} must be a list of names")
    return tuple(str(v) for v in value)


def _module(name: str, node: Node) -> Module:
    where = f"module {name}"
    entry = _mapping(node, where)
    layer, kernel = entry.get("layer"), entry.get("kernel")
    if not isinstance(layer, int) or isinstance(layer, bool) or not isinstance(kernel, bool):
        raise MapError(f"{where}: needs an integer layer and a boolean kernel")
    return Module(
        name,
        layer,
        kernel,
        _names(entry, "depends_on", where),
        _names(entry, "kernel_includes", where),
        _names(entry, "kernel_interface", where),
    )


def module_map(node: Node) -> ModuleMap:
    root = _mapping(node, "modules.yaml")
    modules = _mapping(root.get("modules", {}), "modules")
    rules = _names(root, "rules", "modules.yaml")
    libraries = _mapping(root.get("kernel_libraries", {}), "kernel_libraries")
    external = _mapping(root.get("external", {}), "external")
    allowed: dict[str, tuple[str, ...]] = {}
    for package, entry in external.items():
        fields = _mapping(entry, f"external {package}")
        import_name = fields.get("import", package)
        allowed[str(import_name)] = _names(fields, "allowed_in", f"external {package}")
    return ModuleMap(
        {name: _module(name, entry) for name, entry in modules.items()},
        rules,
        {
            name: _names(_mapping(entry, f"library {name}"), "used_by", f"library {name}")
            for name, entry in libraries.items()
        },
        allowed,
    )


def read_module_map(path: Path) -> ModuleMap:
    return module_map(parse(path.read_text(encoding="utf-8")))
