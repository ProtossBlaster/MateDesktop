"""Picks the platform module and re-exports its interface under one set of names.

The launcher imports this and nothing else platform-shaped, so reading it never means holding two
operating systems in your head at once. Adding a platform is adding a file here, not another
branch in code that already has a job.

The interface, in full:

    data_dir()                        → where this user's Mate data lives
    acquire_single_instance(app_dir)  → False if another copy is already running
    raise_running_instance()          → bring that other copy to the front
    autostart_sync(wanted, log)       → make "start at login" match the user's answer
    on_system_quit(callback, log)     → run callback when the OS asks the app to quit
    stop_child(proc)                  → ask a service process to stop, as politely as the OS allows
"""
from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"
NAME = "Windows" if IS_WINDOWS else "macOS"

if IS_WINDOWS:
    import plat_win as _impl
else:
    import plat_mac as _impl

data_dir = _impl.data_dir
acquire_single_instance = _impl.acquire_single_instance
raise_running_instance = _impl.raise_running_instance
autostart_sync = _impl.autostart_sync
on_system_quit = _impl.on_system_quit


def stop_child(proc) -> None:
    """POSIX gets SIGTERM (the payload can act on it); Windows gets TerminateProcess, which is all
    it has. Kept here rather than duplicated: only Windows needs to say anything about it."""
    if IS_WINDOWS:
        _impl.stop_child(proc)
    else:
        proc.terminate()
