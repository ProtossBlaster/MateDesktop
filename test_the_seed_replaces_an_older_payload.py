"""A shell only ever replaces an older shell, and it must be able to START.

The payload on disk outlives the app: it lives in the data directory, and a new app installed over
an old one finds whatever the old one was running. Until now the seed inside the bundle was used
only when there was no payload at all, so a 1.2.0 installed over a 1.0.0 stuck on Mate 2.10.1 ran
that 2.10.1 — and 1.2.0 no longer carries the third-party cloud library it imports. Both services
died on `ModuleNotFoundError: No module named 'leapmotor_api'`, the port never opened, and the app
exited without drawing anything: "even if I install version 1.2.0 over it, the app no longer
launches" (MateDesktop #10). Reproduced on macOS with the released 1.0.0 and 1.2.0 bundles.

The seed is the floor this shell guarantees it can run. Anything older is replaced by it.

    python3 -m pytest test_the_seed_replaces_an_older_payload.py
"""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))
import updater


def payload(path: Path, version: str) -> Path:
    for part in ("web", "poller"):
        (path / part).mkdir(parents=True, exist_ok=True)
        (path / part / "main.py").write_text(f'MATE_VERSION = "{version}"\n')
    return path


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    """The launcher pointed at a throwaway data directory, with a seed of its own."""
    monkeypatch.setenv("MATE_APP_DIR", str(tmp_path / "data"))
    import launcher
    launcher = importlib.reload(launcher)
    seed_root = tmp_path / "shell"
    payload(seed_root / "payload_seed", "4.7.8")
    monkeypatch.setattr(launcher, "shell_dir", lambda: seed_root)
    return launcher


def test_a_payload_older_than_the_seed_is_replaced(launcher):
    payload(launcher.CURRENT, "2.10.1")
    launcher.ensure_payload(log=lambda _: None)
    assert updater.payload_version(launcher.CURRENT) == "4.7.8"


def test_the_replaced_payload_is_not_left_as_a_rollback_target(launcher):
    """Rolling back onto it is the same failure again, one launch later."""
    payload(launcher.CURRENT, "2.10.1")
    payload(launcher.PREVIOUS, "2.10.0")
    launcher.ensure_payload(log=lambda _: None)
    assert not launcher.PREVIOUS.exists()


def test_a_payload_newer_than_the_seed_is_kept(launcher):
    """The normal case: the app has been updating itself and is ahead of its own installer."""
    payload(launcher.CURRENT, "4.7.18")
    launcher.ensure_payload(log=lambda _: None)
    assert updater.payload_version(launcher.CURRENT) == "4.7.18"


def test_the_seed_itself_is_kept(launcher):
    payload(launcher.CURRENT, "4.7.8")
    (launcher.CURRENT / "web" / "marker").write_text("installed, not re-copied")
    launcher.ensure_payload(log=lambda _: None)
    assert (launcher.CURRENT / "web" / "marker").exists()


def test_a_payload_that_declares_no_version_is_replaced(launcher):
    """An interrupted copy reads as nothing; so does a directory that is not Mate."""
    (launcher.CURRENT / "web").mkdir(parents=True)
    (launcher.CURRENT / "web" / "main.py").write_text("# half a file\n")
    launcher.ensure_payload(log=lambda _: None)
    assert updater.payload_version(launcher.CURRENT) == "4.7.8"


def test_a_first_run_still_installs_the_seed(launcher):
    launcher.ensure_payload(log=lambda _: None)
    assert updater.payload_version(launcher.CURRENT) == "4.7.8"


def test_a_build_with_no_seed_and_no_payload_refuses_to_start(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "shell_dir", lambda: launcher.APP_DIR / "nowhere")
    with pytest.raises(SystemExit):
        launcher.ensure_payload(log=lambda _: None)


def test_a_build_with_no_seed_keeps_what_is_installed(launcher, monkeypatch):
    """Running from source: there is no seed, and the payload on disk is all there is."""
    payload(launcher.CURRENT, "2.10.1")
    monkeypatch.setattr(launcher, "shell_dir", lambda: launcher.APP_DIR / "nowhere")
    launcher.ensure_payload(log=lambda _: None)
    assert updater.payload_version(launcher.CURRENT) == "2.10.1"
