"""A real application window instead of a browser tab.

Mate's interface is a web page, but handing the user a tab at 127.0.0.1:64556 makes it feel
like something that happens to be running on their machine rather than an app they installed.
This puts the same page inside a native window, using the WebView the system already has —
WebKit on macOS, WebView2 on Windows — so the build carries no browser of its own and stays
around 70 MB rather than 200.

The window is not decoration: it is what lets Mate close cleanly. A browser tab has no way of
telling the poller to stop, so quitting the app while a tab stays open would leave the two
services running with nothing on screen.
"""
from __future__ import annotations

import sys

import plat

WINDOW_TITLE = "LeapMotor Mate"
MIN_SIZE = (900, 640)
DEFAULT_SIZE = (1180, 860)


def available() -> bool:
    try:
        import webview  # noqa: F401
        return True
    except Exception:
        return False


def open_window(url: str, on_close=None, log=print) -> bool:
    """Show the app window and block until the user closes it.

    Returns False when no WebView is usable, so the caller can fall back to the browser rather
    than leaving the user with a running poller and nothing to look at.
    """
    try:
        import webview
    except Exception as exc:                                  # noqa: BLE001
        log(f"native window unavailable ({exc}) — falling back to the browser")
        return False

    # Downloads are OFF by default in pywebview, and Mate leans on them more than most: GPX
    # export, the charges/trips CSVs, the full database backup, and the diagnostics ZIP that
    # every bug report asks for. Left at the default, all of those would do exactly nothing when
    # clicked — a silent dead end, and the worst kind for a user who can't tell an app bug from
    # their own mistake. With it on, macOS shows its own save panel.
    webview.settings["ALLOW_DOWNLOADS"] = True
    # Anything genuinely off-site (the update notice, the project page, the licence) belongs in
    # the real browser, not trapped in a window with no address bar or back button.
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True

    win = webview.create_window(
        WINDOW_TITLE, url,
        width=DEFAULT_SIZE[0], height=DEFAULT_SIZE[1],
        min_size=MIN_SIZE,
        # Mate paints its own dark surface; matching it here stops the white flash while the
        # first page loads, which on a dark UI reads as a glitch.
        background_color="#0f172a",
        text_select=True,
    )
    if on_close is not None:
        win.events.closed += on_close
        plat.on_system_quit(on_close, log=log)

    try:
        webview.start()                # blocks on the main thread, as the GUI toolkits require
        return True
    except Exception as exc:                                  # noqa: BLE001
        log(f"window failed to start ({exc}) — falling back to the browser")
        return False


def close(log=print) -> None:
    """Shut the window from code, so the app can end itself.

    Everything else that ends the app is started by the user — the red button, quitting, the
    machine shutting down — and all of those already unblock webview.start() on their own. This
    is for the one case that does not: Mate asking to be removed. Without it the services stop,
    the page behind the window dies, and the user is left staring at a black rectangle they still
    have to close by hand, having just pressed a button that said the app would go away.
    """
    try:
        import webview
        for win in list(webview.windows):
            win.destroy()
    except Exception as exc:                                  # noqa: BLE001
        log(f"could not close the window ({exc})")


def reload(url: str, log=print) -> None:
    """Point the open window at `url` again.

    Rarely needed now that the port is fixed for the app's lifetime, but kept as a safety net.
    It no longer swallows its own failure: the first version did, and when it silently stopped
    working the only symptom was a black window with no clue anywhere as to why.
    """
    try:
        import webview
        if webview.windows:
            webview.windows[0].load_url(url)
    except Exception as exc:                                  # noqa: BLE001
        log(f"could not point the window at {url}: {exc}")
