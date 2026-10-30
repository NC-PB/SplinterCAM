# SPDX-License-Identifier: Apache-2.0
"""The strategy registry: each strategy's declarations, the builder of its typed input and its
planning function (REQ-JOB-013, 014; Peter, AQ-014; DEC-JOB-006)."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from splintercam.cl import ClOperation
from splintercam.foundation import Context, Diagnostic, Result
from splintercam.geometry2d import CurveRows
from splintercam.model import JobData, Operation, ParameterDeclaration
from splintercam.strategies.profile import DECLARATIONS, STRATEGY_ID, ProfileInput, plan_profile


@dataclass(frozen=True, slots=True)
class Strategy[T]:
    """One strategy as `job` calls it."""

    declarations: tuple[ParameterDeclaration, ...]
    build: Callable[[Operation, CurveRows, JobData], T]  # the typed input of one operation
    plan: Callable[[T, Context], Result[ClOperation]]


def profile_input(operation: Operation, contour: CurveRows, job: JobData) -> ProfileInput:
    """`ProfileInput` of a checked operation: the part's loop, the tool with the operation's T
    number, the setup's stock and the operation. A tool not found is a programming error:
    `check_job` found it (REQ-MDL-014; DEC-CL-002)."""
    tool = next((tool for tool in job.tools if tool.number == operation.tool_number), None)
    if tool is None:
        raise ValueError(f"operation {operation.name!r}: no tool T{operation.tool_number}")
    return ProfileInput(contour, tool, job.setup.stock, operation)


REGISTRY: Mapping[str, Strategy[Any]] = MappingProxyType(
    {STRATEGY_ID: Strategy(DECLARATIONS, profile_input, plan_profile)}
)


def relocate(diagnostic: Diagnostic, index: int, name: str) -> Diagnostic:
    """A strategy's diagnostic located as model locates an operation's (REQ-MDL-027; DEC-JOB-006):
    `operation (<name>)` leading becomes `operation <index> (<name>)`, None that alone, any
    other location follows it after a colon."""
    head, where = f"operation ({name})", f"operation {index} ({name})"
    location = diagnostic.location
    if location is None:
        return replace(diagnostic, location=where)
    if location.startswith(head):
        return replace(diagnostic, location=where + location[len(head) :])
    return replace(diagnostic, location=f"{where}: {location}")
