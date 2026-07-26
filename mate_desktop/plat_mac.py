"""Everything macOS-specific, behind the interface plat.py exposes.

Six things differ between macOS and Windows — where data lives, how one instance
is enforced, how a running copy is brought to the front, how the app registers to
start at login, how the system announces a shutdown, and how services are stopped.
They live here and in plat_win.py so the launcher itself stays free of "if we are
on a Mac" — and so a third platform, if it ever comes, adds a file instead of
threading branches through everything.

── Start at login ──────────────────────────────────────────────────────────


This exists because of what the app IS: unlike the Home Assistant add-on or a Docker container,
which run whether anyone is looking or not, a Mac app records only while it is open — and the
one thing a car does on its own schedule is charge overnight. An app the user has to remember to
launch will miss precisely the data they installed it for.

macOS has three ways to do this and only one of them fits an unsigned, self-distributed app:

  * SMAppService (the modern API) wants a signed bundle and a helper embedded in it — neither of
    which this build has yet.
  * A "login item" added through System Events needs Automation consent, so the first time the
    user flips the switch they get a permission dialog about controlling another application,
    which is an alarming thing to be asked in exchange for a checkbox.
  * A LaunchAgent is a plist in the user's own folder. launchd reads that folder at login by
    itself, so WRITING THE FILE IS THE WHOLE JOB — no consent prompt, no launchctl, and nothing
    happens right now that the user did not ask for. It also shows up in System Settings →
    General → Login Items, under "Allow in the Background", so it is discoverable and can be
    turned off from where people look for such things.

The agent runs `open -a <the app>` rather than the executable inside the bundle: that is what
makes macOS treat it as a launched application — Dock icon, activation, the lot — instead of a
stray process that happens to draw a window.

The switch itself lives in Mate's Settings, but only the truth of it does: Mate stores a yes/no
and nothing else. Everything specific to macOS is here, so the Windows shell can honour the same
setting through the registry without Mate having to know the difference — or be re-released.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.leapmotor.mate.login"
AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = AGENTS_DIR / f"{LABEL}.plist"


def app_bundle_path() -> Path | None:
    """The .app this shell is running from, or None when running from source.

    Frozen, sys.executable is <bundle>/Contents/MacOS/<binary>, so the bundle is three levels up.
    From source there is no bundle to register and the feature simply has nothing to point at.
    """
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve()
    bundle = exe.parent.parent.parent          # MacOS → Contents → .app
    return bundle if bundle.suffix == ".app" and bundle.is_dir() else None


def _agent(app: Path) -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": ["/usr/bin/open", "-a", str(app)],
        "RunAtLoad": True,
    }


def is_enabled() -> bool:
    return PLIST_PATH.is_file()


def registered_app() -> Path | None:
    """Which app the existing agent points at — None if there is no agent or it is unreadable."""
    try:
        with PLIST_PATH.open("rb") as fh:
            args = plistlib.load(fh).get("ProgramArguments") or []
        return Path(args[-1]) if args else None
    except Exception:                                          # noqa: BLE001
        return None


def enable(app: Path, log=print) -> bool:
    try:
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = PLIST_PATH.with_suffix(".plist.tmp")
        with tmp.open("wb") as fh:
            plistlib.dump(_agent(app), fh)
        os.replace(tmp, PLIST_PATH)             # atomic: launchd never sees a half-written agent
        log(f"start at login: on ({app.name})")
        return True
    except Exception as exc:                                   # noqa: BLE001
        log(f"start at login: could not be turned on ({exc})")
        return False


def disable(log=print) -> bool:
    try:
        if PLIST_PATH.exists():
            PLIST_PATH.unlink()
        # Best effort: if this session already loaded the agent, drop it too, so System Settings
        # stops listing an item whose file is gone. Removing the file alone is enough for the
        # next login, which is why a failure here is not worth reporting.
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"],
                       capture_output=True, timeout=5)
        log("start at login: off")
        return True
    except Exception as exc:                                   # noqa: BLE001
        log(f"start at login: could not be turned off ({exc})")
        return False


def autostart_sync(wanted: bool, log=print) -> None:
    """Make the agent match what the user asked for — and keep it correct.

    Called on every launch, not just when the switch moves, because the agent holds a PATH: the
    day the user drags the app from Downloads to Applications, an agent written yesterday points
    at nothing, and Mate would silently stop starting at login with no way to tell. Rewriting it
    from where the app actually is now costs nothing and repairs that on its own.
    """
    app = app_bundle_path()
    if app is None:                        # running from source: nothing to register
        return
    if wanted:
        if not is_enabled() or registered_app() != app:
            enable(app, log=log)
    elif is_enabled():
        disable(log=log)


# ── Where the data lives ────────────────────────────────────────────────────────────────

APP_NAME = "LeapMotorMate"
# The two names macOS files an app's caches under: the bundle identifier when it is properly
# bundled, the displayed name otherwise. Both turn up in practice, and removing Mate has to know
# both — see remove_everything(). BUNDLE_ID is read by build_mac.sh rather than repeated there,
# so the identifier the system keys everything on is written down once.
BUNDLE_ID = "com.protossblaster.matedesktop"
DISPLAY_NAME = "LeapMotor Mate"


def data_dir() -> Path:
    """~/Library/Application Support/LeapMotorMate — where macOS expects an app's data, and
    deliberately NOT next to the app: a bundle gets replaced, moved or dragged to the bin, and a
    user's whole driving history must not go with it."""
    return Path.home() / "Library" / "Application Support" / APP_NAME


# ── One instance at a time ──────────────────────────────────────────────────────────────
# Two copies means two pollers on one SQLite file and two cloud sessions on one account, which
# evict each other. An exclusive flock held for the process's whole life: the OS drops it however
# the process dies — crash, kill -9, power cut — so a stale lock can never wedge the app shut,
# which a PID file would.

_lock_handle = None


def acquire_single_instance(app_dir: Path) -> bool:
    """True if this process may run; False when another copy already holds the lock."""
    global _lock_handle
    import fcntl
    app_dir.mkdir(parents=True, exist_ok=True)
    _lock_handle = open(app_dir / "mate.lock", "w")
    try:
        fcntl.flock(_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _lock_handle.close()
        _lock_handle = None
        return False
    _lock_handle.write(f"{os.getpid()}\n")
    _lock_handle.flush()
    return True


def raise_running_instance() -> None:
    """Bring the copy that IS running to the front, so a second launch behaves like a click on
    the Dock icon rather than doing nothing visible."""
    try:
        subprocess.run(["osascript", "-e",
                        'tell application "System Events" to set frontmost of the first process '
                        'whose name is "LeapMotor Mate" to true'],
                       capture_output=True, timeout=5)
    except Exception:  # noqa: BLE001
        pass


# ── The system asking the app to quit ───────────────────────────────────────────────────

_quit_watcher = None        # kept alive: Cocoa's notification centre does not retain observers


def on_system_quit(callback, log=print) -> None:
    """Run `callback` when macOS asks the app to quit — shutdown, restart, log out.

    Closing the window and shutting the Mac down look the same from the user's side and are not
    the same at all underneath. The window's own `closed` event covers the first. The second
    arrives as an Apple Event straight to Cocoa: the process ends without that event ever firing,
    so the services were being killed by the system rather than stopped by us, and the database
    was never consolidated. Measured, not assumed — the shutdown log simply stopped mid-sentence.

    If AppKit isn't importable for any reason, the app keeps working exactly as before; this only
    ever adds a chance to clean up.
    """
    global _quit_watcher
    try:
        from AppKit import NSApplicationWillTerminateNotification
        from Foundation import NSNotificationCenter, NSObject

        class _QuitWatcher(NSObject):
            def willTerminate_(self, notification):     # noqa: N802 — Cocoa selector name
                callback()

        _quit_watcher = _QuitWatcher.alloc().init()
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            _quit_watcher, "willTerminate:", NSApplicationWillTerminateNotification, None)
    except Exception as exc:                                  # noqa: BLE001
        log(f"system-quit hook unavailable ({exc}) — shutdown will be less tidy")


# ── Removing Mate for good ──────────────────────────────────────────────────────────────

def remove_everything(app_dir, log=print) -> None:
    """Delete the data directory and put the app in the Bin.

    This exists because macOS gives an unsigned, non-App-Store app nowhere else to do it. There is
    no uninstaller: an app is dragged to the Bin, and the Bin has never heard of Application
    Support — which is why a Mac accumulates folders belonging to programs it no longer has. (App
    Store apps ARE different: they are sandboxed into ~/Library/Containers and deleting them from
    Launchpad takes the container too. That is the behaviour people remember, and it does not
    apply to us.)

    So the only place left to offer it is inside the app, as its last act.

    The data directory is deleted outright — it is Mate's own, and the user has just confirmed a
    dialog that says so. The APP goes to the Bin rather than being deleted: emptying it is the
    user's decision, not ours, and a 77 MB bundle sitting in the Bin is a recoverable mistake
    while a deleted one is not.
    """
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    app_dir = Path(app_dir)
    try:
        if app_dir.name != APP_NAME or not app_dir.is_dir():
            log(f"refusing to remove {app_dir} — not Mate's own data directory")
        else:
            shutil.rmtree(app_dir, ignore_errors=True)
            log(f"removed {app_dir}")
    except Exception as exc:                                   # noqa: BLE001
        log(f"could not remove {app_dir}: {exc}")

    # …and the caches macOS keeps FOR us, outside Application Support, which the first version of
    # this missed entirely: it removed the data directory and left three megabytes of WebKit cache
    # behind, so "removes everything" was not true. Found by checking a sentence in the README
    # rather than by anything failing.
    #
    # EXACT paths, never a search for "leapmotor". The official Leapmotor app keeps
    # ~/Library/Application Scripts/com.leapmotor.abroad and a group container beside these on a
    # real user's Mac, and a glob written to be thorough would take their application with it.
    home = Path.home()
    for path in (home / "Library" / "Caches" / DISPLAY_NAME,
                 home / "Library" / "Caches" / BUNDLE_ID,
                 home / "Library" / "WebKit" / DISPLAY_NAME,
                 home / "Library" / "WebKit" / BUNDLE_ID,
                 home / "Library" / "Saved Application State" / f"{BUNDLE_ID}.savedState"):
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                log(f"removed {path}")
        except Exception as exc:                               # noqa: BLE001
            log(f"could not remove {path}: {exc}")
    # Crash reports are one file per crash, named with a UUID — matched on the prefix, which is
    # the app's own name and an underscore, so nothing else can be caught by it.
    reports = home / "Library" / "Application Support" / "CrashReporter"
    try:
        for f in reports.glob(f"{DISPLAY_NAME}_*.plist"):
            f.unlink(missing_ok=True)
            log(f"removed {f.name}")
    except Exception:                                          # noqa: BLE001
        pass

    # Only from a real .app; running from a checkout there is nothing to bin, and binning a
    # developer's working copy would be a memorable way to lose an afternoon.
    if not getattr(sys, "frozen", False):
        log("running from source — leaving the working copy alone")
        return
    bundle = Path(sys.executable).resolve()
    for parent in bundle.parents:
        if parent.suffix == ".app":
            bundle = parent
            break
    else:
        log("not inside an .app bundle — nothing to move to the Bin")
        return
    try:
        # Through the Finder, so it lands in the Bin with Put Back available, rather than being
        # unlinked. Never fatal: the data is already gone, and a bundle left behind is something
        # the user can drag away themselves.
        subprocess.run(
            ["osascript", "-e",
             f'tell application "Finder" to delete POSIX file "{bundle}"'],
            capture_output=True, timeout=30)
        log(f"moved {bundle.name} to the Bin")
    except Exception as exc:                                   # noqa: BLE001
        log(f"could not move the app to the Bin: {exc}")
