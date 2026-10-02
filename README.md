# SplinterCAM

An open-source CAM system for CNC milling, licensed Apache-2.0. Release 1 is core 2.5D milling on three axes (facing, profiles, pockets, drilling, chamfers) with output through NCX to Heidenhain, Siemens and Fanuc controls.

Status: early start (October 2026). The research phase, Project Spike, still holds the decisions; this repository starts with the modules whose research is ready: `foundation` first, then the topic 01 part of `geometry2d`. See `docs/plans/active/` for the current plan and `docs/spike/README.md` for what came from the research.

## Prerequisites

- git and git-lfs
- [uv](https://docs.astral.sh/uv/) (it installs the pinned Python version)
- A C++20 compiler: Xcode Command Line Tools on macOS, Visual Studio Build Tools on Windows, GCC or Clang on Linux
- bash to run `tools/`: on Windows, Git Bash

CMake, Ninja, ruff, pyright, clang-format and clang-tidy come through uv at pinned versions. After cloning, run `tools/bootstrap`, then `tools/check`.

## Working with agents

The rules for agents are in `AGENTS.md` (and `CLAUDE.md` for Claude Code). Development rules are in `docs/dev/`, decisions in `docs/adr/` and `docs/spike/`. The agent stops and asks for: new dependencies, changes to `architecture/modules.yaml` and ADRs, golden outputs, and anything touching `LICENSE`, `NOTICE`, CI or the agent settings. Details: [docs/dev/07](docs/dev/07-agent-workflow.md).
