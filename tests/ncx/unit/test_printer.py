# SPDX-License-Identifier: Apache-2.0
"""The number printer's examples (REQ-NCX-008); against exact rational arithmetic in
tests/ncx/property/test_ncx_properties.py."""

import numpy as np
import pytest

from ncx_programs import exact_text as _exact
from ncx_programs import printed as _printed


@pytest.mark.req("REQ-NCX-008")
@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0.0078125, "0.007813"),  # a tie: half to even would give 0.007812
        (-0.0078125, "-0.007813"),
        (5e-7, "0.0"),  # the double nearest 5e-7 lies below it
        (1e-5, "0.00001"),
        (1e-7, "0.0"),
        (-1e-7, "0.0"),  # no "-0"
        (-0.0, "0.0"),
        (0.5, "0.5"),
        (5.0, "5.0"),
        (2.0**-20, "0.000001"),
        (123456.0000004, "123456.0"),
        (8000.0, "8000.0"),
        (-10.0 / 3.0, "-3.333333"),
        (float(np.nextafter(1e9, 0.0)), "1000000000.0"),  # 1e9 - 2^-23 rounds up
    ],
)
def test_the_printer_examples(value: float, text: str) -> None:
    assert _printed([value]) == [text]
    assert _exact(value) == text


@pytest.mark.req("REQ-NCX-008")
def test_the_text_has_no_exponent_and_no_plus() -> None:
    texts = _printed([1e-300, 7e-6, 1.0, 1e8, -2.25e-6])
    assert texts == ["0.0", "0.000007", "1.0", "100000000.0", "-0.000002"]
