# SPDX-License-Identifier: Apache-2.0
"""Put tools/lib on the import path, so these tests import the tools' modules by name.

pytest's own path setting lives in pyproject.toml, which only a person changes (plan 0001, step 3).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "lib"))
