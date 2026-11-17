"""Helpers for features backed by optional dependency groups."""

from importlib import import_module


def import_optional(module, *, extra, purpose=None, package=None):
    """Import *module* or explain which package extra enables the feature."""
    try:
        return import_module(module, package=package)
    except ModuleNotFoundError as exc:
        feature = f" for {purpose}" if purpose else ""
        message = (
            f"Optional dependency {exc.name!r} is required{feature}. "
            f"Install it with `pip install 'multipanel[{extra}]'`."
        )
        raise ModuleNotFoundError(message, name=exc.name) from exc


__all__ = ["import_optional"]
