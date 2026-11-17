import pytest


@pytest.fixture(autouse=True)
def _internal_clipboard():
    """Tests never touch the real system clipboard."""
    from multipanel import clipboard

    clipboard.set_clipboard_backend("internal")
    yield
    clipboard.set_clipboard_backend("internal")
