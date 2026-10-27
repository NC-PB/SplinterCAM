# SPDX-License-Identifier: Apache-2.0
"""A fake `ncx` for the `run_ncx` tests (src/splintercam/ncx/SPEC.md, Test plan), its fixture
registered by tests/ncx/conftest.py: the Python interpreter run on a folder per step, `format`,
`check` and `compile`, which `run_ncx` passes as its first argument, so `python <step> ...` runs
`<step>/__main__.py` in the working folder. It records its arguments and working folder and
prints, sleeps and exits as told. The real interpreter, not a venv launcher, so stopping it
stops the fake on Windows too."""

import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import pytest

from splintercam.ncx import NcxCall, NcxStep

_SCRIPT = """import json, os, sys, time
step = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
with open({conf!r}, encoding="utf-8") as conf:
    behaviour = json.load(conf)[step]
with open(os.path.join({log!r}, step + ".json"), "w", encoding="utf-8") as record:
    json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd()}}, record)
sys.stdout.write(behaviour["stdout"])
sys.stdout.flush()
sys.stderr.write(behaviour["stderr"])
sys.stderr.flush()
time.sleep(behaviour["sleep"])
sys.exit(behaviour["exit"])
"""


@dataclass(frozen=True, slots=True)
class Step:
    """What the fake does for one step."""

    exit: int = 0
    stderr: str = ""
    stdout: str = ""
    sleep: float = 0.0


@dataclass(frozen=True, slots=True)
class FakeNcx:
    call: NcxCall
    log: Path

    def ran(self) -> list[NcxStep]:
        """The steps the fake was started for, in step order."""
        return [step for step in NcxStep if (self.log / f"{step.value}.json").exists()]

    def record(self, step: NcxStep) -> dict[str, object]:
        with (self.log / f"{step.value}.json").open(encoding="utf-8") as recorded:
            return json.load(recorded)


type MakeFake = Callable[..., FakeNcx]


@pytest.fixture
def fake_ncx(tmp_path: Path) -> MakeFake:
    """`fake_ncx(format=Step(...), check=..., compile=...)`: a call to the fake; unnamed steps
    exit 0 silently. `{ncx}` in a step's stderr stands for the call's NCX file. Each call gets
    its own folder, so a property test can make one per example."""

    def make(**steps: Step) -> FakeNcx:
        base = Path(tempfile.mkdtemp(dir=tmp_path))
        work = base / "work dir (x86)"
        ncx_file = work / "RECT_FILLETS.ncx"
        log = base / "log"
        log.mkdir()
        conf = base / "behaviour.json"
        behaviour = {step.value: asdict(steps.get(step.value, Step())) for step in NcxStep}
        for told in behaviour.values():
            told["stderr"] = str(told["stderr"]).replace("{ncx}", str(ncx_file))
        conf.write_text(json.dumps(behaviour), encoding="utf-8")
        for step in NcxStep:
            (work / step.value).mkdir(parents=True)
            script = _SCRIPT.format(conf=str(conf), log=str(log))
            (work / step.value / "__main__.py").write_text(script, encoding="utf-8")
        interpreter = Path(getattr(sys, "_base_executable", sys.executable))
        call = NcxCall(
            executable=interpreter,
            work_dir=work,
            ncx_file=ncx_file,
            machine_file=base / "heidenhain-itnc530.toml",
            output_dir=base / "out",
        )
        return FakeNcx(call, log)

    return make
