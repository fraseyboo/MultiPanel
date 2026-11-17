"""No prints in the library; logging is opt-in (W0 hygiene)."""
import ast
import io
import logging
from pathlib import Path

import pytest

import multipanel
from multipanel.logs import enable_logging

SRC = Path(multipanel.__file__).resolve().parent


def _main_guard(node):
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__")


def test_library_code_does_not_print():
    offenders = []
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def visit(node, guarded):
            guarded = guarded or _main_guard(node)
            if not guarded and isinstance(node, ast.Call) and \
                    isinstance(node.func, ast.Name) and node.func.id == "print":
                offenders.append(f"{path.name}:{node.lineno}")
            for child in ast.iter_child_nodes(node):
                visit(child, guarded)

        visit(tree, False)
    assert offenders == []


def test_enable_logging_shows_library_debug_messages():
    stream = io.StringIO()
    handler = enable_logging("debug", stream)
    try:
        logging.getLogger("multipanel.controls").debug("hello %s", "there")
        logging.getLogger("elsewhere").warning("not ours")
        assert stream.getvalue() == "DEBUG multipanel.controls: hello there\n"
        enable_logging("warning", stream)          # replaces the handler
        logging.getLogger("multipanel.views").info("quiet")
        assert "quiet" not in stream.getvalue()
        assert sum(getattr(h, "_multipanel_handler", False) for h in
                   logging.getLogger("multipanel").handlers) == 1
    finally:
        logger = logging.getLogger("multipanel")
        for h in list(logger.handlers):
            if getattr(h, "_multipanel_handler", False):
                logger.removeHandler(h)
        logger.setLevel(logging.NOTSET)
    with pytest.raises(ValueError):
        enable_logging("chatty")
