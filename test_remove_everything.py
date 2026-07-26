"""Removing Mate has to remove ALL of Mate — and nothing else.

The first version of remove_everything() deleted the data directory and stopped there, leaving
three megabytes of WebKit cache under ~/Library/Caches. "Removes everything" was not true, and it
was found by checking a sentence in the README rather than by anything failing.

The second risk is the opposite one, and worse. macOS also holds
~/Library/Application Scripts/com.leapmotor.abroad and a group container of the same name — those
belong to the OFFICIAL Leapmotor app, which sits beside ours on a real user's Mac. A cleanup
written as a search for "leapmotor" would take somebody else's application with it.

Run from a Mac; skipped elsewhere.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="macOS removal")

import plat_mac  # noqa: E402


def _targets(home: Path):
    """The paths remove_everything() would touch, derived the same way it derives them."""
    return [
        home / "Library" / "Caches" / plat_mac.DISPLAY_NAME,
        home / "Library" / "Caches" / plat_mac.BUNDLE_ID,
        home / "Library" / "WebKit" / plat_mac.DISPLAY_NAME,
        home / "Library" / "WebKit" / plat_mac.BUNDLE_ID,
        home / "Library" / "Saved Application State" / f"{plat_mac.BUNDLE_ID}.savedState",
    ]


def test_it_removes_the_caches_not_only_the_data(tmp_path, monkeypatch):
    """The defect this file exists for. Everything below is set up as macOS would have it."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    data = tmp_path / "Library" / "Application Support" / plat_mac.APP_NAME
    (data / "payload").mkdir(parents=True)
    (data / "leapmotor_mate.db").write_text("x")
    for p in _targets(tmp_path):
        p.mkdir(parents=True, exist_ok=True)
        (p / "junk").write_text("x")
    reports = tmp_path / "Library" / "Application Support" / "CrashReporter"
    reports.mkdir(parents=True)
    (reports / f"{plat_mac.DISPLAY_NAME}_ABC-123.plist").write_text("x")

    plat_mac.remove_everything(data, log=lambda *_: None)

    assert not data.exists(), "the data directory survived"
    for p in _targets(tmp_path):
        assert not p.exists(), f"left behind: {p}"
    assert not list(reports.glob(f"{plat_mac.DISPLAY_NAME}_*.plist")), "crash reports left behind"


def test_it_leaves_the_official_leapmotor_app_alone(tmp_path, monkeypatch):
    """The one that would be a disaster. com.leapmotor.abroad is the official app; it is on the
    same Mac, its name contains 'leapmotor', and it is not ours to touch."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    data = tmp_path / "Library" / "Application Support" / plat_mac.APP_NAME
    data.mkdir(parents=True)
    others = [
        tmp_path / "Library" / "Application Scripts" / "com.leapmotor.abroad",
        tmp_path / "Library" / "Group Containers" / "group.com.leapmotor.abroad",
        tmp_path / "Library" / "Caches" / "com.leapmotor.abroad",
        tmp_path / "Library" / "Application Support" / "LeapMotorSomethingElse",
    ]
    for p in others:
        p.mkdir(parents=True, exist_ok=True)
        (p / "theirs").write_text("not ours")

    plat_mac.remove_everything(data, log=lambda *_: None)

    for p in others:
        assert p.exists(), f"deleted somebody else's data: {p}"
        assert (p / "theirs").read_text() == "not ours"


def test_it_refuses_a_directory_that_is_not_mates(tmp_path, monkeypatch):
    """MATE_APP_DIR can point the data directory anywhere, and this function ends in rmtree."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    wrong = tmp_path / "Documents"
    wrong.mkdir(parents=True)
    (wrong / "important.txt").write_text("keep me")

    plat_mac.remove_everything(wrong, log=lambda *_: None)

    assert (wrong / "important.txt").exists(), "removed a directory that was not Mate's"


def test_missing_paths_are_not_an_error(tmp_path, monkeypatch):
    """A fresh install has no caches yet, and removal still has to finish."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    data = tmp_path / "Library" / "Application Support" / plat_mac.APP_NAME
    data.mkdir(parents=True)
    plat_mac.remove_everything(data, log=lambda *_: None)      # must not raise
    assert not data.exists()


def test_the_bundle_identifier_is_written_down_once():
    """build_mac.sh reads it from here. Two copies would drift, and the caches macOS files under
    the identifier would then be missed by a cleanup looking for the other one."""
    build = (Path(__file__).resolve().parent / "build_mac.sh").read_text()
    assert "com.protossblaster.matedesktop" not in build, "the identifier is repeated in the build"
    assert "BUNDLE_ID" in build, "the build does not read the identifier from plat_mac.py"
