"""Everything Windows-specific, behind the interface plat.py exposes.

The macOS twin is plat_mac.py; between them they cover the six things that genuinely differ.
Everything else — the updater, the service loop, the payload, the window — is shared code, and
that is the point: a `.exe` and a `.app` running the same Mate should differ in how they are
packaged, not in how they behave.

Nothing here needs a compiler or a third-party package: ctypes talks to the Win32 API directly
and winreg is in the standard library, so the build stays a plain PyInstaller run.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "LeapMotorMate"
WINDOW_TITLE = "LeapMotor Mate"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "LeapMotor Mate"


# ── Where the data lives ────────────────────────────────────────────────────────────────

def data_dir() -> Path:
    """%LOCALAPPDATA%\\LeapMotorMate.

    LOCAL rather than roaming: on a domain-joined machine — which is exactly where Mate's kind of
    user often is — a roaming profile is copied to the server at every sign-out, and a driving
    history that grows without limit has no business travelling over the network. It is also the
    Windows counterpart of Application Support in spirit: the app's own data, kept away from the
    executable so replacing or deleting the app never touches it.
    """
    base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


# ── One instance at a time ──────────────────────────────────────────────────────────────
# Same reason as on macOS: two pollers on one SQLite file, and two cloud sessions on one account
# that evict each other. Windows has no flock, but it has a better fit — a named mutex. The kernel
# destroys it when the last handle closes, however the process dies, so a crash can never leave
# something behind that keeps the app from starting again.

_mutex = None
_ERROR_ALREADY_EXISTS = 183


def acquire_single_instance(app_dir: Path) -> bool:
    """True if this process may run; False when another copy already holds the mutex."""
    global _mutex
    app_dir.mkdir(parents=True, exist_ok=True)
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # No "Global\\" prefix: the mutex is per-session, which is what we want. Two people
        # signed in to the same PC each have their own %LOCALAPPDATA% and their own database,
        # so they are not two copies of the same install and must not block each other.
        _mutex = kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}")
        if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(_mutex)
            _mutex = None
            return False
        return bool(_mutex)
    except Exception:                                          # noqa: BLE001
        # Never let a missing API keep the app from starting: worst case the guard is absent,
        # which is where every version before this one already was.
        return True


def raise_running_instance() -> None:
    """Bring the copy that IS running to the front, so a second launch behaves like clicking the
    taskbar button rather than doing nothing visible."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE — un-minimise if it was minimised
            user32.SetForegroundWindow(hwnd)
    except Exception:                                          # noqa: BLE001
        pass


# ── Start at login ──────────────────────────────────────────────────────────────────────
# The macOS side writes a LaunchAgent; here it is a value under HKCU\...\Run. Same properties,
# which is why the setting can be shared: per-user (no administrator rights), applied at the next
# sign-in, and — the part that matters for trust — visible to the user in Settings ▸ Apps ▸
# Startup, where they can switch it off without going anywhere near a registry editor.
#
# HKCU, never HKLM: writing a machine-wide entry would need elevation, and an unsigned app asking
# for administrator rights to tick a checkbox is exactly the behaviour people are right to refuse.

def app_executable() -> Path | None:
    """The .exe this shell runs from, or None from source (nothing to register)."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve()


def _run_key(access):
    """For READING. Raises if the key is absent, which the callers read as 'not enabled' — and
    that is the right answer: no key means no entry means the switch is off."""
    import winreg
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)


def _run_key_for_write():
    """For WRITING, where a missing key must be created rather than refused.

    HKCU\\...\\Run looks permanent and is not: it is an ordinary key that exists because something
    put a value in it, and it goes away again when the last one is removed — Inno's uninstaller
    does exactly that when Mate was the only entry. Found on a machine where the key had genuinely
    vanished, and the symptom is the worst kind: OpenKey raises FileNotFoundError, enable() catches
    it, logs one line nobody reads, and the user's "start at login" switch does nothing at all.

    CreateKeyEx opens an existing key and creates a missing one, which is what every application
    that registers itself here actually does.
    """
    import winreg
    return winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)


def is_enabled() -> bool:
    try:
        import winreg
        with _run_key(winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
        return True
    except Exception:                                          # noqa: BLE001
        return False


def registered_command() -> str | None:
    try:
        import winreg
        with _run_key(winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, RUN_VALUE)[0]
    except Exception:                                          # noqa: BLE001
        return None


def _command_for(exe: Path) -> str:
    # Quoted: "Program Files" and the user's own name both routinely contain spaces, and an
    # unquoted path with a space is the classic way a Run entry silently does nothing.
    return f'"{exe}"'


def enable(exe: Path, log=print) -> bool:
    try:
        import winreg
        with _run_key_for_write() as key:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _command_for(exe))
        log(f"start at login: on ({exe.name})")
        return True
    except Exception as exc:                                   # noqa: BLE001
        log(f"start at login: could not be turned on ({exc})")
        return False


def disable(log=print) -> bool:
    try:
        import winreg
        with _run_key(winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE)
        log("start at login: off")
        return True
    except FileNotFoundError:
        return True                                            # already absent
    except Exception as exc:                                   # noqa: BLE001
        log(f"start at login: could not be turned off ({exc})")
        return False


def autostart_sync(wanted: bool, log=print) -> None:
    """Make the registry match what the user asked for — and keep it correct.

    Rewritten on every launch, not only when the switch moves, for the same reason as on macOS:
    the entry holds a PATH. Move the app, or install a newer one somewhere else, and yesterday's
    entry points at nothing — silently, with Mate simply not starting one morning.
    """
    exe = app_executable()
    if exe is None:                        # running from source: nothing to register
        return
    if wanted:
        if not is_enabled() or registered_command() != _command_for(exe):
            enable(exe, log=log)
    elif is_enabled():
        disable(log=log)


# ── The system asking the app to quit ───────────────────────────────────────────────────

def on_system_quit(callback, log=print) -> None:
    """Nothing to install here, and that is a measured result rather than an assumption.

    Windows announces a shutdown with WM_QUERYENDSESSION / WM_ENDSESSION to each top-level window,
    the counterpart of the Cocoa notification the Mac side has to observe explicitly. The question
    was whether pywebview's Windows backend turns that into the window's `closed` event, which
    would make the shared shutdown path enough — on macOS the equivalent was broken and only a real
    shutdown revealed it, so this was left unimplemented until the same test had been run here.

    Run 26/07, `shutdown /r` (no /f, so the system genuinely ASKS), against the System event log:

        08:34:00  1074  shutdown.exe initiated a restart
        08:34:05        the app logged "database consolidated" / "Mate stopped"
        08:34:07  6006  the Event Log service stopped
        08:34:09    13  the OS shut down
        08:34:10    12  the OS started

    The app closed four seconds before Windows itself started going down, and the database's -wal
    and -shm sidecars were gone afterwards: the checkpoint ran. The shared path is enough.

    One thing to know if this is ever revisited: Windows force-kills an app that has not finished
    closing in about five seconds (WaitToKillAppTimeout), while our stop() allows the children
    eight. It fits today only because stop_child() is TerminateProcess, which returns at once — if
    the children are ever given a gentler, slower death, that grace has to come down to fit inside
    the system's, or a shutdown will interrupt the checkpoint it was meant to protect.
    """
    log("system-quit hook: not needed on Windows (session end arrives as a window close)")


# ── Stopping the services ───────────────────────────────────────────────────────────────

def stop_child(proc: subprocess.Popen) -> None:
    """Windows has no SIGTERM: Popen.terminate() is TerminateProcess, which stops the child where
    it stands with no chance to close anything.

    That is survivable and was measured on the Mac side — an interrupted write leaves SQLite's
    journal to be recovered on the next start, worst case a trip left open and resumed — but it is
    still the blunt instrument, and it is worth knowing that is what happens here rather than
    discovering it from a corrupted-looking database. If it ever needs to be gentler, the route is
    CREATE_NEW_PROCESS_GROUP plus CTRL_BREAK_EVENT, which the payload would have to handle.
    """
    proc.terminate()


# ── Removing Mate for good ──────────────────────────────────────────────────────────────

def remove_everything(app_dir, log=print) -> None:
    """Not used on Windows, and deliberately a no-op that says so.

    Windows has a real uninstaller, reached the way every other program is reached — Settings ▸
    Apps — and it already takes the data with it (see the [UninstallDelete] section in
    installer.iss and the RemoveUserData action in installer.wxs). Mate's Settings therefore does
    not offer the button here: two ways to remove the same app, one of them hidden inside it, is
    worse than one obvious way.

    Kept so plat.py's interface is the same shape on both sides. If it is ever reached, something
    has called it that should not have, and this line is how that gets noticed.
    """
    log("remove_everything: not used on Windows — the uninstaller in Settings > Apps does this")
