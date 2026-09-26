"""Candidate selection is explicit; failed candidates retain the outgoing payload."""
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))
import updater


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    monkeypatch.setenv("MATE_APP_DIR", str(tmp_path))
    import launcher
    launcher = importlib.reload(launcher)
    launcher.CURRENT.mkdir(parents=True)
    return launcher


def payload(path, version):
    for part in ("web", "poller"):
        (path / part).mkdir(parents=True)
        (path / part / "main.py").write_text(f'MATE_VERSION = "{version}"\n')


def test_exact_tag_lookup_does_not_change_stable_endpoint(monkeypatch):
    urls = []
    def response(req, **kwargs):
        urls.append(req.full_url)
        return io.BytesIO(json.dumps({"tag_name": "v4.0.0-rc.1"}).encode())
    monkeypatch.setattr(updater.urllib.request, "urlopen", response)
    assert updater.release_for_tag("v4.0.0-rc.1")["version"] == "4.0.0-rc.1"
    updater.latest_release()
    assert urls[0].endswith("/releases/tags/v4.0.0-rc.1")
    assert urls[1].endswith("/releases/latest")


def test_tag_lookup_rejects_different_release(monkeypatch):
    monkeypatch.setattr(updater, "_latest", lambda _: {"tag": "v4.0.0", "version": "4.0.0"})
    assert updater.release_for_tag("v4.0.0-rc.1") is None


def test_stable_release_follows_its_candidate():
    assert updater.release_order("4.0.0") > updater.release_order("4.0.0-rc.1")
    assert updater.release_order("3.4.50") < updater.release_order("4.0.0-rc.1")


def test_candidate_install_and_rollback(launcher, monkeypatch):
    payload(launcher.CURRENT, "3.4.50")
    monkeypatch.setattr(updater, "release_for_tag", lambda tag: {"tag": tag, "version": "4.0.0-rc.1"})
    monkeypatch.setattr(updater, "latest_release", lambda: pytest.fail("candidate queried stable feed"))
    monkeypatch.setattr(updater, "fetch_payload", lambda tag, dest, **kw: payload(dest, "4.0.0-rc.1"))
    assert launcher.try_update(log=lambda _: None, payload_tag="v4.0.0-rc.1")
    assert updater.payload_version(launcher.CURRENT) == "4.0.0-rc.1"
    assert updater.rollback(launcher.CURRENT, launcher.PREVIOUS, log=lambda _: None)
    assert updater.payload_version(launcher.CURRENT) == "3.4.50"


def test_candidate_missing_dependency_keeps_previous(launcher, monkeypatch):
    payload(launcher.CURRENT, "3.4.50")
    monkeypatch.setattr(updater, "release_for_tag", lambda tag: {"tag": tag, "version": "4.0.0-rc.1"})
    monkeypatch.setattr(updater, "fetch_payload", lambda tag, dest, **kw: payload(dest, "4.0.0-rc.1"))
    monkeypatch.setattr(updater, "unsatisfied_requirements", lambda _: ["missing-library"])
    assert not launcher.try_update(log=lambda _: None, payload_tag="v4.0.0-rc.1")
    assert updater.payload_version(launcher.CURRENT) == "3.4.50"
    assert not launcher.STAGED.exists()


@pytest.mark.skipif(not os.environ.get("MATE_REPO"), reason="set MATE_REPO for real payload smoke test")
def test_real_payload_serves_with_desktop_child_environment(launcher, monkeypatch):
    """Exercise both actual entry points in disposable data, with no account or credentials."""
    root = Path(os.environ["MATE_REPO"]).resolve()
    for part in ("web", "poller"):
        shutil.copytree(root / part, launcher.CURRENT / part,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    executable = os.environ.get("MATE_FROZEN_EXECUTABLE")
    if executable:
        assert Path(executable).is_file(), executable
        monkeypatch.setattr(sys, "executable", str(Path(executable).resolve()))
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    port = launcher.free_port(0)
    procs = launcher.spawn(port)
    try:
        assert launcher.wait_until_serving(port, 25), (launcher.APP_DIR / "mate-web-console.log").read_text()
        assert all(p.poll() is None for p in procs), (launcher.APP_DIR / "mate-poller-console.log").read_text()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            assert response.status == 200
    finally:
        launcher.stop(procs)


def test_cli_explicit_candidate_overrides_skip_update(launcher, monkeypatch):
    monkeypatch.setenv("MATE_SKIP_UPDATE", "1")
    monkeypatch.setattr(launcher.plat, "acquire_single_instance", lambda _: True)
    monkeypatch.setattr(updater, "newer_shell", lambda _: None)
    calls = []
    monkeypatch.setattr(launcher, "try_update", lambda **kw: calls.append(kw) or True)
    class Started(Exception):
        pass
    def services(**kwargs):
        assert kwargs == {"fresh_payload": True}
        raise Started
    monkeypatch.setattr(launcher, "Services", services)
    with pytest.raises(Started):
        launcher.main(["--payload-tag", "v4.0.0-rc.1"])
    assert calls == [{"payload_tag": "v4.0.0-rc.1"}]
