"""The shell↔payload contract is checked against the payload, not against memory.

`payload_deps.py` says what the payload imports, so PyInstaller packages it. Its docstring says the
list was "generated from a full AST scan of web/ and poller/" — once, by hand, at the beginning.
Nothing re-ran that scan, so when Mate 3.4.10 started importing PIL directly (car_image.py, to
measure which way the charging animation runs), the contract did not learn about it. It worked
anyway: Pillow arrives as an extra of leapmotor-api[image] and PyInstaller bundled the whole
package. By luck, not by contract — and the day that extra changes shape, the first sign would be
an app dying on someone's Mac with no clue why.

This re-runs the scan every time. It needs the Mate source next door; without it, it skips rather
than passing on nothing.

    MATE_REPO=~/leapmotor-mate python3 -m pytest test_payload_contract.py
"""
import ast
import os
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
MATE = pathlib.Path(os.environ.get("MATE_REPO", pathlib.Path.home() / "leapmotor-mate"))

# Imported by the shell itself, never by the payload — they are not part of the contract.
SHELL_ONLY = {"mate_desktop", "webview", "PyInstaller"}
# The payload's own top-level modules: they import each other by bare name, and they ARE the
# payload — the shell is not expected to carry them.
PAYLOAD_LOCAL = None    # filled in below, from the filenames themselves


def _declared() -> set[str]:
    """Top-level module names named in payload_deps.py."""
    tree = ast.parse((HERE / "mate_desktop" / "payload_deps.py").read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            out.add(n.module.split(".")[0])
    return out


def _payload_imports() -> tuple[set[str], set[str]]:
    """(every top-level module the payload imports, its own local modules)."""
    files = [p for d in ("web", "poller") for p in (MATE / d).rglob("*.py")]
    local = {p.stem for p in files}
    used: set[str] = set()
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                used |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                used.add(n.module.split(".")[0])
    return used, local


@pytest.mark.skipif(not (MATE / "web").is_dir(),
                    reason=f"Mate source not found at {MATE} — set MATE_REPO")
def test_every_module_the_payload_imports_is_declared_in_the_contract():
    used, local = _payload_imports()
    missing = sorted(m for m in used - _declared() - local - SHELL_ONLY
                     if m not in sys.builtin_module_names)
    assert not missing, (
        "the payload imports these and payload_deps.py does not name them — a frozen build would "
        "ship without them:\n  " + "\n  ".join(missing) +
        "\n\nAdd them to mate_desktop/payload_deps.py (and, if they are third-party, check the "
        "updater's _IMPORT_NAME map too)."
    )


@pytest.mark.skipif(not (MATE / "web").is_dir(), reason="Mate source not found")
def test_the_contract_does_not_name_things_the_payload_stopped_using():
    """The other direction, as a warning rather than a rule: a name that no longer appears makes
    the frozen build bigger for nothing, and makes the contract harder to trust."""
    used, _ = _payload_imports()
    stale = sorted(_declared() - used - SHELL_ONLY)
    assert not stale, ("payload_deps.py names modules the payload no longer imports: "
                       + ", ".join(stale))
