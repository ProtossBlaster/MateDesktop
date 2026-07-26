"""Tests for the Windows platform module — runnable from a Mac.

Everything Windows-shaped that can be checked without Windows is checked here: the shape of the
registry command, where the data goes, when the login entry is rewritten. What genuinely cannot
be faked — a real mutex, a real registry, a real shutdown — is left for the VM, and named as such
in the notes rather than pretended away.

The point of testing this from macOS at all is that the whole file is one long opportunity for a
silent mistake: a Run entry with an unquoted path, or roaming AppData instead of local, does not
raise anything. It just quietly does the wrong thing on someone else's machine.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))
import plat_win  # noqa: E402


class _FakeRegistry:
    """Stands in for HKCU\\...\\Run: a dict with the winreg calls the module makes.

    `key_exists` is not decoration. The first version of this fake opened happily whether or not
    the key was there, which is more forgiving than winreg — and that difference hid a real defect:
    on a machine where HKCU\\...\\Run did not exist, enable() raised inside OpenKey, the exception
    was swallowed, and the user's start-at-login switch did nothing. Every test here passed
    throughout. A fake that cannot fail the way the real thing fails cannot catch what the real
    thing catches.
    """

    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 3
    HKEY_CURRENT_USER = object()

    def __init__(self, key_exists=True):
        self.values = {}
        self.key_exists = key_exists

    def _handle(self):
        registry = self

        class _Key:
            def __enter__(self):
                return registry

            def __exit__(self, *a):
                return False
        return _Key()

    # winreg's own surface, as used by plat_win
    def OpenKey(self, root, path, reserved, access):    # noqa: N802
        if not self.key_exists:
            raise FileNotFoundError(path)               # exactly what winreg does
        return self._handle()

    def CreateKeyEx(self, root, path, reserved, access):   # noqa: N802
        self.key_exists = True                          # opens it, or brings it into being
        return self._handle()

    def QueryValueEx(self, key, name):                  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        return (self.values[name], self.REG_SZ)

    def SetValueEx(self, key, name, reserved, kind, value):   # noqa: N802
        self.values[name] = value

    def DeleteValue(self, key, name):                   # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


@pytest.fixture
def registry(monkeypatch):
    fake = _FakeRegistry()
    monkeypatch.setitem(sys.modules, "winreg", fake)
    return fake


def test_the_data_goes_in_local_appdata(monkeypatch):
    """LOCAL, not roaming. On a domain-joined machine — where a good share of Windows users are —
    roaming AppData is copied to the server at every sign-out, and a driving history that grows
    without limit has no business travelling over the network at each logoff."""
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\someone\AppData\Local")
    assert plat_win.data_dir() == Path(r"C:\Users\someone\AppData\Local") / "LeapMotorMate"


def test_the_data_dir_survives_a_missing_variable(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert plat_win.data_dir().name == "LeapMotorMate"
    assert "AppData" in str(plat_win.data_dir())


def test_the_login_entry_quotes_the_path(registry, monkeypatch):
    r"""The classic Windows own-goal: C:\Program Files\... written unquoted, and the entry runs
    C:\Program with the rest as arguments. It fails silently at the next sign-in, which is the
    worst possible moment to find out."""
    exe = Path(r"C:\Program Files\LeapMotor Mate\LeapMotor Mate.exe")
    assert plat_win.enable(exe, log=lambda *_: None) is True
    assert registry.values[plat_win.RUN_VALUE] == f'"{exe}"'


def test_disabling_removes_the_entry(registry):
    plat_win.enable(Path(r"C:\app\Mate.exe"), log=lambda *_: None)
    assert plat_win.disable(log=lambda *_: None) is True
    assert plat_win.RUN_VALUE not in registry.values


def test_disabling_when_it_was_never_on_is_not_an_error(registry):
    assert plat_win.disable(log=lambda *_: None) is True


def test_sync_follows_the_switch(registry, monkeypatch):
    exe = Path(r"C:\app\Mate.exe")
    monkeypatch.setattr(plat_win, "app_executable", lambda: exe)

    plat_win.autostart_sync(True, log=lambda *_: None)
    assert plat_win.is_enabled() is True

    plat_win.autostart_sync(False, log=lambda *_: None)
    assert plat_win.is_enabled() is False


def test_sync_rewrites_a_moved_app(registry, monkeypatch):
    """Same hazard as the LaunchAgent on the Mac: the entry holds a path, and people move
    executables. Rewritten on every launch so a moved app repairs itself."""
    monkeypatch.setattr(plat_win, "app_executable", lambda: Path(r"C:\old\Mate.exe"))
    plat_win.autostart_sync(True, log=lambda *_: None)

    monkeypatch.setattr(plat_win, "app_executable", lambda: Path(r"C:\new\Mate.exe"))
    plat_win.autostart_sync(True, log=lambda *_: None)

    assert registry.values[plat_win.RUN_VALUE] == r'"C:\new\Mate.exe"'


def test_sync_does_nothing_from_source(registry, monkeypatch):
    """From a checkout there is no .exe to register, and pointing a login entry at a developer's
    working copy would be a nasty surprise on their own machine."""
    monkeypatch.setattr(plat_win, "app_executable", lambda: None)
    plat_win.autostart_sync(True, log=lambda *_: None)
    assert plat_win.is_enabled() is False


def test_it_writes_to_the_users_own_key_not_the_machines():
    """HKCU, never HKLM: a machine-wide entry needs elevation, and an unsigned app asking for
    administrator rights to tick a checkbox is exactly what people should refuse."""
    assert plat_win.RUN_KEY.startswith("Software\\Microsoft\\Windows")
    source = (Path(__file__).parent / "mate_desktop" / "plat_win.py").read_text()
    assert "HKEY_LOCAL_MACHINE" not in source


def test_the_interface_matches_the_mac_one():
    """plat.py re-exports one set of names; a function missing on one side would only show up as
    an AttributeError on someone else's operating system."""
    import plat_mac
    for name in ("data_dir", "acquire_single_instance", "raise_running_instance",
                 "autostart_sync", "on_system_quit"):
        assert callable(getattr(plat_win, name)), f"plat_win is missing {name}"
        assert callable(getattr(plat_mac, name)), f"plat_mac is missing {name}"


def test_a_missing_win32_api_never_blocks_startup(monkeypatch, tmp_path):
    """Everything here reaches into ctypes. If any of it is unavailable, the app must still open:
    the guard is a nicety, and losing it is not worth refusing to run."""
    import builtins
    real_import = builtins.__import__

    def no_ctypes(name, *a, **k):
        if name == "ctypes":
            raise ImportError("no ctypes here")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_ctypes)
    assert plat_win.acquire_single_instance(tmp_path) is True
    plat_win.raise_running_instance()          # must not raise


# ── the Run key is not permanent ────────────────────────────────────────────────────────
# HKCU\...\Run looks like part of Windows and is not: it exists because something put a value in
# it, and it goes away when the last one is taken out — which our own Inno uninstaller does when
# Mate was the only entry. Measured on the test VM, where the key had genuinely vanished.

def test_it_can_be_switched_on_when_the_run_key_does_not_exist(monkeypatch):
    """The defect this pair of tests exists for. enable() used OpenKey, which refuses a key that
    is not there; the exception was caught and logged, and from the user's side the switch simply
    did nothing — no error, no entry, no clue."""
    fake = _FakeRegistry(key_exists=False)
    monkeypatch.setitem(sys.modules, "winreg", fake)

    assert plat_win.enable(Path(r"C:\Users\x\AppData\Local\Programs\Mate\Mate.exe"), log=lambda *_: None)
    assert fake.key_exists, "the key should have been created"
    assert plat_win.is_enabled()


def test_switching_off_when_the_run_key_does_not_exist_is_not_an_error(monkeypatch):
    """The mirror case, which must NOT create the key: there is nothing to remove, and an
    uninstall-time tidy-up has no business bringing a key into existence to then leave it empty."""
    fake = _FakeRegistry(key_exists=False)
    monkeypatch.setitem(sys.modules, "winreg", fake)

    assert plat_win.disable(log=lambda *_: None)
    assert not fake.key_exists
    assert not plat_win.is_enabled()


def test_sync_turns_it_on_from_nothing(monkeypatch, tmp_path):
    """End to end through the path the app actually takes every ten seconds while it is open."""
    fake = _FakeRegistry(key_exists=False)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    exe = tmp_path / "LeapMotor Mate.exe"
    monkeypatch.setattr(plat_win, "app_executable", lambda: exe)

    plat_win.autostart_sync(True, log=lambda *_: None)
    assert fake.values["LeapMotor Mate"] == f'"{exe}"'
