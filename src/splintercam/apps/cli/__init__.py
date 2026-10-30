# SPDX-License-Identifier: Apache-2.0
"""apps/cli: `splintercam run`, the headless runner over `job.run_job` (see SPEC.md)."""

from ._cli import entry, main

__all__ = ["entry", "main"]
