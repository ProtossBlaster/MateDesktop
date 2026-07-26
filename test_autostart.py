"""Tests for the shell's half of "start at login", macOS side (plat_mac).

Run with:  python3 -m pytest test_autostart.py -q

These matter more than they look. The agent holds a PATH, and the app is distributed as a file
people drag around: Downloads today, Applications tomorrow. An agent that keeps pointing at
yesterday's location fails silently — Mate simply doesn't start one morning, with nothing
anywhere to say why. Most of what follows is about that.
"""
import plistlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))
import plat_mac as autostart  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Point the agent at a throwaway LaunchAgents folder — never the real one."""
    agents = tmp_path / "LaunchAgents"
    monkeypatch.setattr(autostart, "AGENTS_DIR", agents)
    monkeypatch.setattr(autostart, "PLIST_PATH", agents / f"{autostart.LABEL}.plist")
    # …and never actually talk to launchd from a test.
    monkeypatch.setattr(autostart.subprocess, "run", lambda *a, **k: None)
    return tmp_path


def _bundle(root: Path, name="LeapMotor Mate.app") -> Path:
    app = root / name
    (app / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    return app


def test_enabling_writes_an_agent_that_opens_the_app(home):
    app = _bundle(home)
    assert autostart.enable(app, log=lambda *_: None) is True
    assert autostart.is_enabled() is True

    data = plistlib.loads(autostart.PLIST_PATH.read_bytes())
    assert data["Label"] == autostart.LABEL
    assert data["RunAtLoad"] is True
    # `open -a <app>` and not the binary inside: that is what makes macOS treat it as a launched
    # application — Dock icon, activation — rather than a stray process drawing a window.
    assert data["ProgramArguments"][:2] == ["/usr/bin/open", "-a"]
    assert data["ProgramArguments"][-1] == str(app)


def test_disabling_removes_it(home):
    app = _bundle(home)
    autostart.enable(app, log=lambda *_: None)
    assert autostart.disable(log=lambda *_: None) is True
    assert autostart.is_enabled() is False


def test_disabling_when_it_was_never_on_is_not_an_error(home):
    assert autostart.disable(log=lambda *_: None) is True
    assert autostart.is_enabled() is False


def test_sync_follows_the_switch(home, monkeypatch):
    app = _bundle(home)
    monkeypatch.setattr(autostart, "app_bundle_path", lambda: app)

    autostart.autostart_sync(True, log=lambda *_: None)
    assert autostart.is_enabled() is True

    autostart.autostart_sync(False, log=lambda *_: None)
    assert autostart.is_enabled() is False


def test_sync_rewrites_a_stale_path(home, monkeypatch):
    old, new = _bundle(home / "Downloads"), _bundle(home / "Applications")
    autostart.enable(old, log=lambda *_: None)
    monkeypatch.setattr(autostart, "app_bundle_path", lambda: new)

    autostart.autostart_sync(True, log=lambda *_: None)
    assert autostart.registered_app() == new


def test_sync_does_nothing_from_source(home, monkeypatch):
    """Running the launcher from a checkout there is no bundle to register, and writing an agent
    pointing at a developer's working copy would be a nasty surprise on their own machine."""
    monkeypatch.setattr(autostart, "app_bundle_path", lambda: None)
    autostart.autostart_sync(True, log=lambda *_: None)
    assert autostart.is_enabled() is False


def test_an_unreadable_agent_is_not_a_crash(home):
    autostart.AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    autostart.PLIST_PATH.write_text("this is not a plist")
    assert autostart.registered_app() is None
    assert autostart.is_enabled() is True          # the file is there, whatever is inside it


def test_a_half_written_agent_is_never_visible(home):
    """launchd reads this folder on its own. Writing in place would give it a window in which
    the file exists but is empty — so the write goes to a temporary name and is moved into
    place, which the filesystem does atomically."""
    app = _bundle(home)
    autostart.enable(app, log=lambda *_: None)
    assert list(autostart.AGENTS_DIR.glob("*.tmp")) == []
    assert plistlib.loads(autostart.PLIST_PATH.read_bytes())["Label"] == autostart.LABEL


def test_the_shell_reads_the_switch_from_mates_own_settings(tmp_path, monkeypatch):
    """The two halves are separate processes: Mate writes the answer, the shell reads it back.
    This is the seam — if either side renames the key or the table, the switch silently stops
    working, and nobody would notice until an unattended overnight charge went missing."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))
    import sqlite3
    import launcher

    db = tmp_path / "leapmotor_mate.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    con.commit()
    monkeypatch.setattr(launcher, "DB_PATH", db)

    assert launcher.autostart_wanted() is False          # absent means no
    con.execute("INSERT INTO settings VALUES ('desktop_autostart', '1')")
    con.commit()
    assert launcher.autostart_wanted() is True
    con.execute("UPDATE settings SET value='0' WHERE key='desktop_autostart'")
    con.commit()
    assert launcher.autostart_wanted() is False
    con.close()


def test_a_missing_database_is_not_consent(tmp_path, monkeypatch):
    """First launch, before the account exists: no database, no answer. The shell must not
    invent one — least of all a yes."""
    import launcher
    monkeypatch.setattr(launcher, "DB_PATH", tmp_path / "nope.db")
    assert launcher.autostart_wanted() is False


# ── certificates the poller can actually reach ──────────────────────────────────────────

def test_no_certificate_is_shipped_unless_the_build_put_one_there(tmp_path, monkeypatch):
    """The app certificate is the USER's, not Mate's: gitignored, fetched once per person from
    markoceri/leapmotor-certs, and asked for by the setup wizard on first run — as under Docker
    and Home Assistant. A build that copies it from the developer's machine hands one person's
    credentials to everyone who downloads the app, which is what this pins shut."""
    import launcher
    monkeypatch.setattr(launcher, "APP_DIR", tmp_path)
    monkeypatch.setattr(launcher, "CURRENT", tmp_path / "payload" / "current")
    monkeypatch.setattr(launcher, "shell_dir", lambda: tmp_path / "shell")   # no certs inside

    env = launcher.child_env("poller", 4000)
    assert "CERT_PATH" not in env
    assert "KEY_PATH" not in env


def test_a_bundled_certificate_is_used_when_one_really_is_there(tmp_path, monkeypatch):
    """The branch stays for a build that deliberately includes its own certificate — and for the
    reason it was written: the poller looks in DATA_CERT_DIR and <payload>/certs, neither of which
    exists in this app, so without being told it has no certificate at all. That only shows up on
    a RE-LOGIN — every time the machine wakes from sleep."""
    import launcher
    shell = tmp_path / "shell" / "certs"
    shell.mkdir(parents=True)
    (shell / "app.crt").write_text("cert")
    (shell / "app.key").write_text("key")
    monkeypatch.setattr(launcher, "APP_DIR", tmp_path)
    monkeypatch.setattr(launcher, "CURRENT", tmp_path / "payload" / "current")
    monkeypatch.setattr(launcher, "shell_dir", lambda: tmp_path / "shell")

    env = launcher.child_env("poller", 4000)
    assert env["CERT_PATH"] == str(shell / "app.crt")


def test_the_users_own_certificates_still_win(tmp_path, monkeypatch):
    """CERT_PATH is an explicit override and beats DATA_CERT_DIR outright, so setting it
    unconditionally would shadow whatever the setup wizard wrote for this user."""
    import launcher
    certs = tmp_path / "certs"
    certs.mkdir(parents=True)
    (certs / "app.crt").write_text("user cert")
    shell = tmp_path / "shell" / "certs"
    shell.mkdir(parents=True)
    (shell / "app.crt").write_text("bundled")
    monkeypatch.setattr(launcher, "APP_DIR", tmp_path)
    monkeypatch.setattr(launcher, "CURRENT", tmp_path / "payload" / "current")
    monkeypatch.setattr(launcher, "shell_dir", lambda: tmp_path / "shell")

    env = launcher.child_env("poller", 4000)
    assert "CERT_PATH" not in env
    assert env["DATA_CERT_DIR"] == str(certs)
