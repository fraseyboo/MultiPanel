import numpy as np
import pytest

from multipanel.colormap_utils import make_colormap


def test_multiknot_range_uses_outer_scalar_values():
    colors = make_colormap(
        c_range=(-3024.0, -2901.0, 1891.0, 2505.0),
        color="viridis", total_colors=5)

    assert colors[:, 0] == pytest.approx(
        np.linspace(-3024.0, 2505.0, 5))


def test_colormap_requires_two_samples_and_two_range_values():
    with pytest.raises(ValueError, match="total_colors"):
        make_colormap(total_colors=1)
    with pytest.raises(ValueError, match="c_range"):
        make_colormap(c_range=(4.0,))
