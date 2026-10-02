# SPDX-License-Identifier: Apache-2.0
"""Unit tests for CancellationToken: flag shape and dtype, cancellation, read-only view
(REQ-FND-006)."""

import numpy as np
import pytest

from splintercam.foundation import CancellationToken


@pytest.mark.req("REQ-FND-006")
def test_fresh_token_is_not_cancelled() -> None:
    token = CancellationToken()
    assert token.is_cancelled is False
    assert token.flag.shape == (1,)
    assert token.flag.dtype == np.uint8
    assert token.flag[0] == 0


@pytest.mark.req("REQ-FND-006")
def test_cancel_sets_is_cancelled_and_the_flag() -> None:
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True
    assert token.flag[0] == 1


@pytest.mark.req("REQ-FND-006")
def test_flag_view_is_read_only() -> None:
    token = CancellationToken()
    with pytest.raises(ValueError, match="read-only"):
        token.flag[0] = 1


@pytest.mark.req("REQ-FND-006")
def test_flag_view_reflects_later_cancellation() -> None:
    token = CancellationToken()
    flag = token.flag
    assert flag[0] == 0
    token.cancel()
    assert flag[0] == 1


@pytest.mark.req("REQ-FND-006")
def test_cancelling_twice_is_fine_and_the_token_stays_cancelled() -> None:
    token = CancellationToken()
    token.cancel()
    token.cancel()
    assert token.is_cancelled is True
    assert token.flag[0] == 1


@pytest.mark.req("REQ-FND-006")
def test_cancelled_flag_cannot_be_made_writeable_and_stays_cancelled() -> None:
    token = CancellationToken()
    token.cancel()
    flag = token.flag
    with pytest.raises(ValueError, match="WRITEABLE"):
        flag.flags.writeable = True
    assert token.is_cancelled is True
    assert token.flag[0] == 1
    # A later cancel() (idempotent, but exercises the writeable-toggle path again) is still
    # reflected through the same view.
    token.cancel()
    assert flag[0] == 1
