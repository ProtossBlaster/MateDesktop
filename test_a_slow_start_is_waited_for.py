"""A service that is still starting is waited for; one that has died is not (MateDesktop #13).

Petr's Windows PC took 21-26 seconds from launching the services to their first line, from one day
to the next, with the same payload that had opened in 5 seconds the day before. The app gave them a
fixed 25 seconds, stopped them a moment before the web server answered, and said Mate could not
start: every launch, for three days. The wait now lasts while the web server is alive, up to a
limit far above any start measured, and ends at once when it exits, so a broken payload is still
rolled back without delay.
"""
import importlib
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    monkeypatch.setenv("MATE_APP_DIR", str(tmp_path))
    import launcher
    return importlib.reload(launcher)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve_after(port, seconds):
    """A stand-in web server: alive from the start, listening only after `seconds`."""
    code = (f"import socket, time\ntime.sleep({seconds})\n"
            f"s = socket.socket(); s.bind(('127.0.0.1', {port})); s.listen()\ntime.sleep(30)\n")
    return subprocess.Popen([sys.executable, "-c", code])


def test_a_service_still_starting_after_the_old_grace_is_waited_for(launcher):
    """Scaled down: a service that answers only after a while, alive all along, is waited for."""
    port = _free_port()
    web = _serve_after(port, 2.5)
    try:
        assert launcher.wait_until_serving(port, web, limit=20) is True
    finally:
        web.kill()


def test_a_service_that_died_ends_the_wait_at_once(launcher):
    port = _free_port()
    web = subprocess.Popen([sys.executable, "-c", "raise SystemExit(1)"])
    start = time.monotonic()
    assert launcher.wait_until_serving(port, web, limit=60) is False
    assert time.monotonic() - start < 5, "a dead web server must not be waited for"


def test_the_limit_is_far_above_any_start_measured(launcher):
    """26 s is the slowest measured on #13; the window must outlast a fresh payload AND its rollback."""
    assert launcher.STARTUP_LIMIT_S >= 120
