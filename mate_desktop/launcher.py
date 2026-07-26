"""LeapMotor Mate desktop — the shell that runs the payload and keeps it current.

This is run.sh's job, done in Python so it can ship inside a .app: start the poller and the
web server as children, hold them together, and re-exec on the relaunch code the app uses
when the account or demo mode changes.

Everything Mate needs to be told about its surroundings already travels through environment
variables (DB_PATH, CERT_DIR, WEB_PORT), so the payload itself needs no desktop-specific
changes — the '/data' paths littered through the source are only defaults.

Data lives where each system expects an app's data to live (see plat.py), NOT next to the app:
the app itself gets replaced, moved or deleted, and a user's whole driving history must not go
with it. Everything that differs between macOS and Windows is in plat_mac.py / plat_win.py.
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plat  # noqa: E402
import payload_deps  # noqa: E402,F401 — makes the build carry what the payload will import
import updater  # noqa: E402
import window  # noqa: E402

APP_NAME = "LeapMotorMate"
# The SHELL's own version, deliberately independent of Mate's. The two move at completely
# different speeds — Mate ships most days, this ships when the bundled libraries change (6 times
# in 176 releases) or when the launcher itself is fixed. Tying them together would mean
# publishing a new app for every Mate release with nothing changed inside it.
#
# It exists mainly for support: "it stopped updating" has two very different causes, and only
# this number tells them apart — a shell too old to run the newest Mate, or a real fault.
SHELL_VERSION = "1.0.0"
# Where a NEW SHELL is downloaded from. Only ever shown when an update was REFUSED because this
# shell is too old to run it — the one case the user has to act on. Mate cannot know this address:
# the app is released on its own schedule, from its own repository, so the shell hands it over
# (MATE_DESKTOP_DOWNLOAD_URL) rather than Mate hard-coding a guess. Points at Mate's own releases
# until the app has a repository of its own — CHANGE THIS ONE LINE then, and nothing else.
DOWNLOAD_URL = "https://github.com/ProtossBlaster/leapmotor-mate/releases/latest"
# MATE_APP_DIR exists so the update cycle can be exercised against a throwaway directory
# without touching a real installation's database.
APP_DIR = Path(os.environ.get("MATE_APP_DIR") or plat.data_dir())
PAYLOAD = APP_DIR / "payload"
CURRENT = PAYLOAD / "current"
PREVIOUS = PAYLOAD / "previous"
STAGED = PAYLOAD / "staged"
DB_PATH = APP_DIR / "leapmotor_mate.db"
LOG_PATH = APP_DIR / "desktop.log"
RELAUNCH_CODE = 42          # same contract as run.sh: the app asking to be restarted
# …and its sibling: the app asking to be REMOVED, data and all. Only Mate's own Settings sends it,
# and only after a confirmation. It exists because macOS has no uninstaller to hook: an app is
# dragged to the Bin, and the Bin knows nothing about Application Support. The only place left to
# offer "take it all away" is inside the app itself.
UNINSTALL_CODE = 43
DEFAULT_PORT = 4000
STARTUP_GRACE_S = 25        # how long a fresh payload gets to answer before we call it broken


def log(msg: str) -> None:
    """Write a line to the app's log — and never, ever fail doing it.

    Both halves of this are Windows lessons, learned the hard way in one evening. UTF-8 is
    explicit because Python on Windows opens text files in the SYSTEM code page: a single arrow
    in "2.8.9 → 2.9.0" raised UnicodeEncodeError, the exception travelled up out of the update,
    and the app died before it had drawn anything. And the print goes in a try because a windowed
    build has no console at all — writing to a stream that is not there is another way to end an
    app that has done nothing wrong.

    A logger is a bystander. It can be silent, but it must not be the thing that kills the app.
    """
    line = f"{datetime.now().strftime('%H:%M:%S')} [mate] {msg}"
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001 — no console, or one that can't spell the message
        pass
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
    except OSError:
        pass


def shell_dir() -> Path:
    """Where the bundled read-only bits live — inside the .app once frozen, the repo in dev."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def free_port(preferred: int = DEFAULT_PORT) -> int:
    """Mate's usual port if it's free, else whatever the OS hands us.

    A desktop machine is not a container: 4000 may well belong to something the user already
    runs. Failing to start with 'address in use' would be an opaque dead end for exactly the
    audience this build exists for.
    """
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return preferred


def child_env(part: str, port: int) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CURRENT / part)
    env["DB_PATH"] = str(DB_PATH)
    env["DATA_CERT_DIR"] = str(APP_DIR / "certs")     # user-supplied certs, persistent
    env["CERT_DIR"] = str(shell_dir() / "certs")      # bundled fallback, read-only
    # …and the same fallback again, spelled the way the POLLER reads it. CERT_DIR is understood
    # by the web side alone; the poller's own resolver goes DATA_CERT_DIR → <payload>/certs, and
    # in this app there is no certs/ next to the payload — it ships inside the bundle, which the
    # payload knows nothing about. So the poller had no certificates at all.
    #
    # Nothing looked wrong day to day: the first login works without them, and the session that
    # login opens keeps working. What breaks is RECOVERY — the re-login the poller attempts after
    # the connection drops, which is exactly what a Mac does every time it wakes from sleep. Found
    # that way: after four minutes asleep, "Re-login failed: Missing local app certificate
    # material". The session happened to survive on its own that time. It would not always.
    #
    # Set only when the user has no certificates of their own, because CERT_PATH/KEY_PATH are
    # explicit overrides and win outright — setting them unconditionally would shadow the certs
    # the setup wizard writes to DATA_CERT_DIR. Re-evaluated on every spawn, so the wizard's own
    # relaunch picks them up immediately.
    # …and only when the shell actually HAS a fallback to offer. It normally does not: the app
    # certificate is the Leapmotor app's own TLS pair — the same for every user, published at
    # markoceri/leapmotor-certs — which the setup wizard asks people to upload once, exactly as
    # under Docker and Home Assistant. This app does not redistribute it: doing so would make it
    # the only channel handing out a third party's key material, and would pin every install to
    # the copy that happened to be on the build machine. The branch stays for a build that
    # deliberately includes a certificate of its own.
    bundled_crt = shell_dir() / "certs" / "app.crt"
    if not (APP_DIR / "certs" / "app.crt").exists() and bundled_crt.exists():
        env["CERT_PATH"] = str(bundled_crt)
        env["KEY_PATH"] = str(shell_dir() / "certs" / "app.key")
    env["WEB_PORT"] = str(port)
    env["PYTHONUNBUFFERED"] = "1"
    # Mate's own logs are full of arrows and symbols — "State: unknown → parked_active" is
    # printed on every transition — and Python on Windows encodes streams in the system code
    # page, where none of that exists. Every such line raised inside the logger. Nothing was
    # lost (the file handler survives it) but each one printed a traceback, on a machine where
    # the console output is the first place anyone looks when something is wrong.
    #
    # Fixed HERE rather than in Mate: the payload is the same code that runs on Home Assistant
    # and in Docker, where this has never been a problem, and it should not have to learn about
    # Windows code pages. The shell knows which platform it is on — that is its job — and these
    # cover every line of the payload, present and future.
    #
    # BOTH are needed, and the first one alone was not enough — the test said so. PYTHONIOENCODING
    # governs stdout and stderr; the failure was in logging's own FILE handler, which opens its
    # file with the system default and never looks at that variable. PYTHONUTF8 is the bigger
    # hammer (PEP 540): it makes UTF-8 the default for every file the process opens, which is
    # what a log full of arrows actually needs.
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # Root certificates, carried rather than borrowed. Python verifies HTTPS through OpenSSL,
    # which knows only the certificate authorities already installed on the machine — while
    # Windows itself fetches missing ones on demand, a service OpenSSL cannot use. Measured
    # inside the payload on a fresh Windows: 17 authorities loaded, against the ~150 a browser
    # trusts. The result was HTTPS that worked for some hosts and not others, with no pattern a
    # user could see: charging-station lookups, the Italian PUN registry, Open-Meteo's altitude
    # and temperature, and Mate's own update check all failed with "certificate verify failed",
    # while the cloud login carried on working — requests brings its own bundle, urllib does not.
    #
    # certifi is that same bundle, already in the build because requests depends on it. Pointing
    # the payload at it makes every library agree on one trust store, on both platforms.
    try:
        import certifi
        env["SSL_CERT_FILE"] = certifi.where()
    except Exception:                                          # noqa: BLE001
        log("certifi not available — HTTPS will rely on the system trust store")
    # Tells the UI it is running inside the app rather than on HA or bare Docker, so the version
    # badge can say "restart to apply" instead of sending the user to the releases page for an
    # update this build fetches on its own.
    env["MATE_DESKTOP"] = "1"
    env["MATE_DESKTOP_VERSION"] = SHELL_VERSION
    # Which desktop, because one thing genuinely differs. Windows has a real uninstaller in
    # Settings ▸ Apps that already takes the data with it; macOS has none — an app is dragged to
    # the Bin, and the Bin knows nothing about Application Support. So Mate offers "remove
    # everything" on the Mac and stays quiet on Windows, where offering it would mean two ways to
    # remove the same app with one of them hidden inside it.
    env["MATE_DESKTOP_PLATFORM"] = plat.NAME
    # …and, when an update could NOT be taken, which one. That is the single case the user has to
    # act on, because it will never arrive by itself.
    if BLOCKED_UPDATE:
        env["MATE_UPDATE_BLOCKED"] = BLOCKED_UPDATE
        env["MATE_DESKTOP_DOWNLOAD_URL"] = DOWNLOAD_URL
    return env


def wait_until_serving(port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.4)
    return False


# ── update ──────────────────────────────────────────────────────────────────────────────

def ensure_payload(log=log) -> None:
    """First run: seed the payload from the copy baked into the shell, so the app works offline."""
    if CURRENT.exists():
        return
    seed = shell_dir() / "payload_seed"
    if not seed.is_dir():
        raise SystemExit("no payload installed and none bundled — broken build")
    CURRENT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(seed, CURRENT)
    log(f"first run — installed bundled payload {updater.payload_version(CURRENT)}")


def try_update(log=log) -> bool:
    """Fetch a newer payload if there is one and this shell can run it. Never fatal."""
    have = updater.payload_version(CURRENT)
    rel = updater.latest_release()
    if not rel or not rel.get("version"):
        log("update check skipped (GitHub unreachable)")
        return False
    if updater.version_tuple(rel["version"]) <= updater.version_tuple(have or "0"):
        log(f"up to date ({have})")
        return False

    log(f"new version available: {have} → {rel['version']}")
    shutil.rmtree(STAGED, ignore_errors=True)
    try:
        updater.fetch_payload(rel["tag"], STAGED, log=log)
    except Exception as exc:                       # noqa: BLE001 — a failed update must not stop the app
        log(f"download failed, staying on {have}: {exc}")
        shutil.rmtree(STAGED, ignore_errors=True)
        return False

    # Is this actually Mate? Checked before anything else, because an incomplete download
    # answers "yes" to every other question — no code means no requirements to fail on.
    broken = updater.payload_looks_complete(STAGED)
    if broken:
        log(f"UPDATE REJECTED — {rel['version']} download is incomplete ({broken}); staying on {have}")
        shutil.rmtree(STAGED, ignore_errors=True)
        return False

    # The guard that keeps this design honest: refuse a payload this shell can't satisfy,
    # rather than installing it and dying on an import the user can do nothing about.
    unmet = updater.unsatisfied_requirements(STAGED)
    if unmet:
        log(f"UPDATE REFUSED — {rel['version']} needs: {', '.join(unmet)}")
        log("staying on the current version; a new app download is required for this release")
        global BLOCKED_UPDATE
        BLOCKED_UPDATE = rel["version"]      # the UI turns this into a call to action
        shutil.rmtree(STAGED, ignore_errors=True)
        return False

    updater.install_payload(STAGED, CURRENT, PREVIOUS, log=log)
    return True


# ── run ─────────────────────────────────────────────────────────────────────────────────

CHILD_FLAG = "--mate-child"


def run_as_child() -> int:
    """Second half of the frozen-app trick — see spawn() for why this exists.

    Invoked as `<app> --mate-child <part> <script>`: put the payload's own directory first on
    the import path (a frozen app builds sys.path itself, so PYTHONPATH alone won't do it),
    then hand over to the payload's main exactly as `python main.py` would.
    """
    import runpy
    part, script = sys.argv[2], sys.argv[3]
    sys.path.insert(0, str(CURRENT / part))
    sys.argv = [script]
    runpy.run_path(script, run_name="__main__")
    return 0


DEMO_DB = None          # set on first use — the sample database lives beside the real one

# Version the app wanted but could not take (too old a shell). Passed to the UI so the badge can
# ask for a new download — the one update that never arrives on its own.
BLOCKED_UPDATE = ""


def demo_requested() -> bool:
    """Whether the Try-the-demo button has asked for sample data.

    The web writes a flag file next to the database and asks to be relaunched; run.sh reads it
    on the way back up. This launcher replaced run.sh and did not carry that across, which is
    why the demo simply did nothing on the desktop build — the button worked, the restart
    happened, and the app came back on the real database as if nothing had been asked.
    """
    if os.environ.get("MATE_DEMO", "") not in ("", "0", "false", "False"):
        return True
    return (DB_PATH.parent / "demo.flag").exists()


def seed_demo(log=log) -> Path:
    """Build the sample database the demo runs on, exactly as run.sh does before starting web."""
    demo_db = DB_PATH.parent / "demo.db"
    env = dict(os.environ, PYTHONPATH=str(CURRENT / "poller"),
               MATE_DEMO="1", DB_PATH=str(demo_db), PYTHONUNBUFFERED="1")
    script = CURRENT / "poller" / "seed_demo.py"
    cmd = ([sys.executable, CHILD_FLAG, "poller", str(script)]
           if getattr(sys, "frozen", False) else [sys.executable, str(script)])
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"demo seeding failed: {(r.stderr or r.stdout or '').strip()[:200]}")
    else:
        log("demo mode — sample data ready")
    return demo_db


def spawn(port: int, demo: bool = False) -> list[subprocess.Popen]:
    """Start poller and web as separate processes, as run.sh does in the container.

    In demo mode only the web runs, against the sample database: there is no account and no car
    to poll, and starting the poller would have it hammering a cloud it cannot log in to.

    Frozen, `sys.executable` is the app bundle rather than a python binary, so launching
    `[sys.executable, "main.py"]` would just start a second launcher. Instead the app re-runs
    ITSELF with a marker argument and dispatches to run_as_child() — the standard way to get
    child processes out of a one-binary build, and it keeps the two services genuinely
    separate: the poller can crash or be relaunched without taking the web UI with it.
    """
    frozen = getattr(sys, "frozen", False)
    parts = ("web",) if demo else ("poller", "web")
    demo_db = seed_demo() if demo else None
    procs = []
    for part in parts:
        target = CURRENT / part / "main.py"
        cmd = ([sys.executable, CHILD_FLAG, part, str(target)] if frozen
               else [sys.executable, str(target)])
        env = child_env(part, port)
        if demo:
            env["MATE_DEMO"] = "1"
            env["DB_PATH"] = str(demo_db)
        # A windowed build has no console, so the children inherit standard streams that are not
        # there. On macOS that is harmless; on Windows it is fatal — uvicorn writes its startup
        # banner to stdout before serving anything, that write fails, and the web server dies
        # without a word: the poller's log had its usual lines, Mate's own log had two, and the
        # port simply never opened. Giving them a real file to write to costs nothing and turns
        # the same silence into a readable log the next time something goes wrong here.
        console = open(APP_DIR / f"mate-{part}-console.log", "ab", buffering=0)
        p = subprocess.Popen(cmd, env=env, cwd=str(CURRENT / part),
                             stdin=subprocess.DEVNULL, stdout=console, stderr=console)
        log(f"{part} started (pid {p.pid})" + (" [demo]" if demo else ""))
        procs.append(p)
    return procs


def stop(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            plat.stop_child(p)
    deadline = time.time() + 8
    for p in procs:
        while p.poll() is None and time.time() < deadline:
            time.sleep(0.2)
        if p.poll() is None:
            p.kill()


# ── one instance at a time ──────────────────────────────────────────────────────────────
# Two copies of the app means two pollers on one SQLite file and two cloud sessions on one
# account — which evict each other, the very thing session_share exists to prevent inside a
# single install. It happened in testing: a window closed during a service restart left a
# poller behind, and re-opening the app started a second one on the same database.
#
# The lock is an exclusive flock held for the process's whole life. The OS drops it when the
# process dies however it dies — crash, kill -9, power cut — so a stale lock can't ever wedge
# the app shut, which a PID file would.
def checkpoint_db() -> None:
    """Fold the write-ahead log back into the database file on a clean exit.

    Not needed for safety — SQLite recovers the WAL by itself, and that was measured against
    this very app — but it leaves ONE file holding everything instead of three. It matters the
    day someone copies the folder by hand to move Mate to another machine: with the data still
    in the sidecar, copying just the .db saves an empty database.
    """
    try:
        import sqlite3
        con = sqlite3.connect(str(DB_PATH), timeout=5)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.close()
        log("database consolidated")
    except Exception as exc:  # noqa: BLE001
        log(f"checkpoint skipped: {exc}")



# ── start at login ──────────────────────────────────────────────────────────────────────
# The switch is in Mate's Settings, but Mate only records the answer: it writes `desktop_autostart`
# and stops there. Everything that knows what a LaunchAgent is lives in autostart.py, so the
# Windows shell will honour the same setting its own way without Mate needing to be re-released —
# and Home Assistant and Docker, where the whole question is meaningless, never see the switch.
#
# The shell reads it back rather than being told, because the two halves are separate processes
# and the answer has to survive both of them restarting. Reading is cheap (one row, read-only)
# and settles the two cases that matter: what the user chose at some point in the past, applied
# on every launch, and what they choose right now, applied while the app is open rather than
# leaving them to wonder whether the switch did anything.
AUTOSTART_SETTING = "desktop_autostart"
_AUTOSTART_POLL_S = 10


def autostart_wanted() -> bool:
    """Read the switch from Mate's own settings table. False whenever it can't be read —
    a missing database (first launch, before the account exists) is not consent."""
    try:
        import sqlite3
        if not DB_PATH.exists():
            return False
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=3)
        try:
            row = con.execute("SELECT value FROM settings WHERE key=?",
                              (AUTOSTART_SETTING,)).fetchone()
        finally:
            con.close()
        return bool(row) and str(row[0]).strip() in ("1", "true", "True", "on")
    except Exception:                                          # noqa: BLE001
        return False


class Services(threading.Thread):
    """Runs the poller and the web server for as long as the app is open.

    They live on a thread because macOS insists the window own the main one. The thread also
    absorbs the relaunch cycle Mate uses when the account or demo mode changes: the services
    come back on a possibly different port and the window is simply pointed at the new address,
    so from the user's side the app just reloads itself.
    """

    def __init__(self, fresh_payload: bool):
        super().__init__(daemon=True)
        self.fresh_payload = fresh_payload
        self.ready = threading.Event()     # set once the UI is reachable
        self.url = ""
        self.exit_code = 0
        # NB: not '_stop' — threading.Thread already has a private _stop() and shadowing
        # it breaks join(). Caught by the close-during-restart test, not by review.
        self._quit = threading.Event()
        self.uninstall = False             # set when Mate asked to be removed (exit code 43)
        self._procs: list[subprocess.Popen] = []
        self._spawn_lock = threading.Lock()   # serialises "am I quitting?" against "start them"

    def stop(self) -> None:
        """Final and irreversible: after this, no service may be started again.

        The flag is set FIRST and under the same lock the spawn path takes. Without that, an X
        pressed while the services were mid-restart killed the outgoing processes and then the
        thread happily started fresh ones — which outlived the app as an invisible poller. The
        lock closes that window: either stop() wins and spawn() refuses, or spawn() finishes and
        stop() sees the new processes and kills those.
        """
        with self._spawn_lock:
            self._quit.set()
            procs = list(self._procs)
        stop(procs)

    def run(self) -> None:
        fresh = self.fresh_payload
        # Pick the port ONCE and keep it for the app's whole life. Mate restarts its own
        # services whenever the account, the password or demo mode changes, and a fresh port
        # each time meant the window was left pointing at a dead one — a black rectangle, which
        # is exactly what leaving demo mode looked like. With the address fixed, the page simply
        # reconnects on its own and there is nothing to re-point.
        port = free_port()
        if port != DEFAULT_PORT:
            log(f"port {DEFAULT_PORT} busy — using {port}")
        while not self._quit.is_set():
            with self._spawn_lock:
                if self._quit.is_set():
                    return                          # asked to quit while we were getting ready
                self._procs = spawn(port, demo=demo_requested())
            if self._quit.is_set():                 # …or in the instant right after
                stop(self._procs)
                return

            if not wait_until_serving(port, STARTUP_GRACE_S):
                log(f"payload did not answer on port {port} within {STARTUP_GRACE_S}s")
                stop(self._procs)
                if fresh and updater.rollback(CURRENT, PREVIOUS, log=log):
                    fresh = False
                    continue                       # try again on the restored payload
                self.exit_code = 1
                self.ready.set()
                return

            self.url = f"http://127.0.0.1:{port}"
            log(f"Mate {updater.payload_version(CURRENT)} serving on {self.url}")
            if self.ready.is_set():
                window.reload(self.url, log=log)   # belt and braces: the port no longer changes
            self.ready.set()

            code = self._watch()
            if self._quit.is_set():
                return
            if code == UNINSTALL_CODE:
                # Mate has been asked to remove itself. Close the window from here: nothing else
                # will, and the alternative is a black rectangle the user has to dismiss by hand
                # right after pressing a button that promised the app would go.
                log("removal requested from Settings")
                self.uninstall = True
                window.close(log=log)
                return
            if code != RELAUNCH_CODE:
                self.exit_code = code
                return
            log("relaunch requested — restarting services")
            fresh = False

    def _watch(self) -> int:
        next_autostart_check = 0.0
        while not self._quit.is_set():
            for p in self._procs:
                code = p.poll()
                if code is not None:
                    log(f"a service exited (code {code}) — stopping the other")
                    stop(self._procs)
                    return code
            # The user may flip "start at login" while the app is open, and a switch whose effect
            # only appears after a restart is a switch people press twice and then distrust.
            now = time.monotonic()
            if now >= next_autostart_check:
                next_autostart_check = now + _AUTOSTART_POLL_S
                if not demo_requested():        # demo writes to its own database — not the truth
                    plat.autostart_sync(autostart_wanted(), log=log)
            time.sleep(0.5)
        return 0


def main() -> int:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not plat.acquire_single_instance(APP_DIR):
        log("Mate is already running — bringing that window to the front")
        plat.raise_running_instance()
        return 0
    log(f"MateDesktop {SHELL_VERSION} ({plat.NAME}) — data directory: {APP_DIR}")
    ensure_payload()

    fresh = False
    if os.environ.get("MATE_SKIP_UPDATE") != "1":
        fresh = try_update()

    services = Services(fresh_payload=fresh)
    services.start()
    services.ready.wait(timeout=STARTUP_GRACE_S + 10)

    if not services.url:
        log("services never came up — nothing to show")
        services.stop()
        return services.exit_code or 1

    # One tidy way out, whichever of the three ways the app is asked to end: the user closes the
    # window, the user quits the app, or the Mac shuts down. Idempotent because more than one of
    # them can fire in the same exit — the window's `closed` event and Cocoa's terminate
    # notification both arrive on a normal quit.
    shutdown_done = threading.Event()

    def shutdown() -> None:
        if shutdown_done.is_set():
            return
        shutdown_done.set()
        services.stop()
        checkpoint_db()
        log("Mate stopped")

    use_browser = os.environ.get("MATE_BROWSER") == "1" or not window.available()
    if not use_browser:
        log("opening the app window")
        if not window.open_window(services.url, on_close=shutdown, log=log):
            use_browser = True
        else:
            shutdown()
            if services.uninstall:
                plat.remove_everything(APP_DIR, log=log)
            return 0

    log(f"opening {services.url} in the browser")
    webbrowser.open(services.url)
    services.join()                                # no window to close: live as long as they do
    return services.exit_code


REMOVE_AUTOSTART_FLAG = "--remove-autostart"
UNINSTALL_FLAG = "--uninstall-cleanup"


def remove_autostart() -> int:
    """Take the start-at-login registration away and exit. Nothing else — no window, no services.

    Called by the uninstaller, and it exists because of a genuine limitation rather than a
    preference. Windows Installer can remove registry values it OWNS; ours is written by the app
    when the user moves the switch, so the .msi never owned it, and the one declarative way to get
    rid of it — removing the whole key — would take every other application's start-at-login entry
    with it. HKCU\\...\\Run is shared, and that failure would be silent and untraceable.

    So the uninstaller asks the app to undo its own registration, using the code that made it.
    Never fatal: a leftover entry is untidy, a failed uninstall is worse.
    """
    try:
        plat.autostart_sync(False, log=log)
    except Exception as exc:                                   # noqa: BLE001
        log(f"could not remove the start-at-login entry: {exc}")
    return 0


def uninstall_cleanup() -> int:
    """Remove everything Mate keeps outside its own folder, and exit.

    Uninstalling has to leave nothing behind — the data directory included. Silvio's call, and the
    right one for Windows, where an application that survives its own removal is a bad citizen.

    ⚠️ The CALLER is responsible for only invoking this on a REAL uninstall. A Windows Installer
    major upgrade removes the old version before laying down the new one, so a cleanup wired to
    "uninstall" alone would wipe the user's driving history on every single update — silently, and
    with the new version starting up looking factory-fresh. installer.wxs conditions this on
    REMOVE="ALL" AND NOT UPGRADINGPRODUCTCODE, which is the pair that tells the two apart.

    Never fatal, and deliberately narrow: only APP_DIR, which is Mate's own directory and holds
    nothing that was not put there by Mate.
    """
    try:
        plat.autostart_sync(False, log=log)
    except Exception as exc:                                   # noqa: BLE001
        log(f"could not remove the start-at-login entry: {exc}")
    target = APP_DIR
    try:
        # A last sanity check on the path before recursively deleting it. MATE_APP_DIR can point
        # this anywhere, and "rm -rf $SOMETHING_UNSET" is a well-known way to ruin a machine.
        if target.name != APP_NAME or not target.is_dir():
            log(f"refusing to remove {target} — not Mate's own data directory")
            return 0
        shutil.rmtree(target, ignore_errors=True)
        print(f"removed {target}", flush=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"could not remove {target}: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    # Child dispatch must come first: this same binary is both the launcher and, re-run with
    # the marker argument, each of the two services.
    if len(sys.argv) > 3 and sys.argv[1] == CHILD_FLAG:
        sys.exit(run_as_child())
    # …and before anything that opens a window, takes the single-instance lock or touches the
    # database: these run while the app is being deleted from underneath it.
    if len(sys.argv) > 1 and sys.argv[1] == REMOVE_AUTOSTART_FLAG:
        sys.exit(remove_autostart())
    if len(sys.argv) > 1 and sys.argv[1] == UNINSTALL_FLAG:
        sys.exit(uninstall_cleanup())
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:                               # noqa: BLE001
        # A windowed build has nowhere to print a traceback: the process simply vanishes, and on
        # Windows that is what "the app doesn't start and I don't know why" looks like from both
        # sides. Anything that gets this far goes in the log, where the user can find it and a
        # bug report can carry it.
        import traceback
        log(f"FATAL: {type(exc).__name__}: {exc}")
        for line in traceback.format_exc().splitlines():
            log(f"  {line}")
        sys.exit(1)
