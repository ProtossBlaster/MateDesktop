**Install this one to get Mate 4.25.0.** Mate 4.25.0 is a security release: a web page on another site
could drive a Mate with no password, and the web libraries it runs on had published advisories. The
desktop app carries those libraries itself, so the new ones need a new app. Desktop 1.2.2 refuses Mate
4.25.0 and shows *A newer version of the app is required — download it*: this is that version.

### What it carries

| Library | Desktop 1.2.2 | Desktop 1.2.3 |
|---|---|---|
| FastAPI / Starlette | 0.115.0 / 0.38.6 | 0.162.2 / 1.10.0 |
| python-multipart | 0.0.9 | 0.0.33 |
| Jinja2 | 3.1.4 | 3.1.6 |
| Pillow | 12.3.0 | 13.0.0 |
| cryptography | 48.0.1 | 50.0.2 |

The installer carries Mate v4.25.0. On a Mac it also starts again: Mate 4.24.0 waited for its own lock
there, and its web never opened. What changes in Mate is in its
[release notes](https://github.com/ProtossBlaster/leapmotor-mate/blob/main/docs/releases/v4.25.0.md).

### Installing it

Drag it over the old app in Applications on a Mac, or run the installer on Windows: your history and
settings stay where they are. The app is still not signed with a paid certificate, so the first launch
on a Mac asks once: click **Done**, then **System Settings → Privacy & Security → Open Anyway**.

### Nothing else changes

The same windows and the same data folder.
