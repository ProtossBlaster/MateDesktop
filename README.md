# LeapMotor Mate — desktop app

[Mate](https://github.com/ProtossBlaster/leapmotor-mate) packaged as an ordinary desktop app, for
people who don't run Home Assistant or Docker. Download, double-click, sign in with your Leapmotor
account. Same Mate, same data, same updates — no containers, no add-ons, nothing to configure.

> **Early build.** It works, and it has been tested end to end on both systems. Read *[What this
> build is not](#what-this-build-is-not)* before installing: that section is the difference between
> this being useful to you or a disappointment.

---

## Download

| | |
|---|---|
| **Windows** | `LeapMotor-Mate-<version>-x64.msi` — 64-bit, Windows 10 or later. Installs on Windows on ARM too, through its x64 emulation, which needs **Windows 11**. |
| **macOS** | `LeapMotor-Mate-<version>-arm64.dmg` — **Apple Silicon only** (M1 and later). It will not open on an Intel Mac. |

There is also a `LeapMotor-Mate-Setup-<version>-x64.exe`: the same app in an Inno Setup installer
rather than a Windows Installer package. Take the `.msi` unless you have a reason not to.

Both are on the [releases page](https://github.com/ProtossBlaster/MateDesktop/releases/latest).

### Checking what you downloaded

Neither package is signed, so this is the one check available. Every release lists the SHA-256 of
each file, both in its notes and in a `SHA256SUMS` file. Compare, and the value must match
character for character.

**Windows** — in PowerShell, in the folder you downloaded to:

```powershell
Get-FileHash .\LeapMotor-Mate-*.msi -Algorithm SHA256 | Format-List
```

**macOS** — in Terminal:

```bash
shasum -a 256 ~/Downloads/LeapMotor-Mate-*.dmg
```

Worth knowing what this does and does not tell you. It catches a corrupted download, and a file
that was swapped somewhere along the way — on a mirror, in a forum post, on a stick. It does
**not** prove the file came from us: anyone able to replace the download could also edit the page
listing its checksum. Only a code signature, which the operating system checks by itself on every
launch, proves that — and neither of these builds has one.

---

## First launch

Neither build is signed — code-signing certificates are a paid subscription per platform, and Mate
is free. Both systems will therefore stop you once, and once only.

### Windows

Running the installer brings up a blue **"Windows protected your PC"** panel. That is SmartScreen
saying it has not seen this file before, not that anything is wrong with it.

1. Click **More info**.
2. Click **Run anyway**.

The installer needs no administrator rights: it installs under your own user account. If something
ever asks you for an administrator password to install Mate, that is not Mate.

### macOS

1. Drag **LeapMotor Mate** onto **Applications**.
2. Double-click it. macOS refuses, saying it cannot be checked for malicious software — click
   **Done**, *not* "Move to Bin".
3. Open  → **System Settings** → **Privacy & Security**, scroll down to **Security**. There is a
   line about LeapMotor Mate being blocked, with **Open Anyway** next to it. Click it and confirm.

> Right-click → Open, the old shortcut for this, no longer works on current macOS. The route
> through System Settings is the one that does.

---

## Setting it up

Two steps, the same as on Home Assistant or Docker, and the app walks you through both.

**1 — The Leapmotor app certificate.** Mate asks for two files, `app.crt` and `app.key`. They are
the same for everyone and have nothing to do with your account; the setup screen links straight to
[markoceri/leapmotor-certs](https://github.com/markoceri/leapmotor-certs), where they live. Download
both and drop them into the two boxes (or paste their text). Once only.

*Why they aren't already inside the app:* they are not this project's to hand out, and a copy
baked into a download would go quietly stale the day they are changed — with no way to tell from
the outside why Mate had stopped working.

**2 — A Leapmotor account, and it must be one Mate has to itself.**

> ⚠️ **Not the account you are signed into on the official phone app.** Leapmotor allows about one
> active session per account, so a second client — the app, another add-on, a Docker container,
> any integration — fights Mate for it. They evict each other in a loop, the car goes offline to
> Mate, and you get gaps in the history with no error to explain them. Add a second account to the
> car in the official app and give that one to Mate.

Email, password and the operation PIN, which is the one you use in the app to authorise remote
commands — locking, climate and the rest.

Mate then reads your car from the cloud and shows you which one it found. The **battery** is the
part it cannot always settle by itself: where your model has one European variant it fills the
capacity in, and where there are several it lists them and you pick. If it cannot work out the
car at all, you type the capacity yourself — it is on the certificate of conformity, and it can
be changed later in **Settings ▸ Battery**.

Then it starts recording.

---

## What this build is not

**It is not a service. It records only while the app is open.** Close it and recording stops, like
any other app you close. That matters more than it sounds: home charges usually happen overnight,
so if the machine sleeps, those charges never appear — and they cannot be filled in afterwards,
because the cloud keeps no history to replay.

There is a **Start at login** switch in Settings, which helps but does not solve it. If you want
Mate watching around the clock, run it on something that stays on — a Home Assistant box, a
Raspberry Pi, a NAS — and use this build to try Mate out first. Your data comes with you:
**Settings → Export database**.

---

## Where things are

| | Windows | macOS |
|---|---|---|
| The app | `%LOCALAPPDATA%\Programs\LeapMotor Mate` | `/Applications` |
| Your data | `%LOCALAPPDATA%\LeapMotorMate` | `~/Library/Application Support/LeapMotorMate` |

Mate uses port 4000, or the next free one if something already has it. It talks to Leapmotor's
cloud, to GitHub to check for updates, and to whichever optional services you switch on.

---

## Removing it

> **Back up first if you want to keep the driving history.** Removing Mate deletes it, and it
> cannot be recovered — the cloud keeps no history to replay. **Settings → Export / Backup**.

**Updating is not removing.** A newer version installed over an older one keeps everything.

### Windows

**Settings ▸ Apps ▸ Installed apps ▸ LeapMotor Mate ▸ Uninstall.** The ordinary route, and it takes
everything with it: the app, the Start-menu and desktop shortcuts, the start-at-login entry, and
your data. Nothing is left behind.

### macOS

**Inside Mate: Settings ▸ 🖥️ App ▸ Remove Mate and its data.** It deletes the data, puts the app in
the Bin and closes. Empty the Bin when you are sure — until you do, the app can still be put back.

It has to be done from inside the app because macOS offers nowhere else. There is no uninstaller:
dragging an app to the Bin deletes the app and leaves `Application Support` exactly where it is,
which is why a Mac fills up with folders belonging to programs it no longer has.

**If Mate will not start**, that button is out of reach. Then do it by hand:

```bash
rm -rf ~/Library/Application\ Support/LeapMotorMate
rm -rf ~/Library/Caches/LeapMotor\ Mate ~/Library/Caches/com.protossblaster.matedesktop
rm -rf ~/Library/WebKit/LeapMotor\ Mate ~/Library/WebKit/com.protossblaster.matedesktop
rm -f  ~/Library/Application\ Support/CrashReporter/LeapMotor\ Mate_*.plist
rm -rf /Applications/LeapMotor\ Mate.app
```

The caches are the window's, kept by macOS under both the app's name and its identifier. That is
the whole list — no preferences file, no login item left behind (the app removes its own when the
switch is off), nothing under `/Library` outside your home folder.

> If you also have the **official Leapmotor app**, leave
> `~/Library/Application Scripts/com.leapmotor.abroad` and
> `~/Library/Group Containers/group.com.leapmotor.abroad` alone — those are its, not Mate's.

---

## Updates

**Mate updates itself.** Each time you open it, it checks for a new release and fetches it before
starting — a few megabytes, a second or two. Nothing to download by hand.

What you download here is the *shell*: the runtime and the libraries. It changes rarely (six times
in Mate's first 176 releases), which is why Mate can ship almost daily without you reinstalling
anything. The badge next to the version tells you where you stand:

- **amber** — a new Mate is out; it will be running the next time you open the app.
- **red** — the new Mate needs a newer shell than this one. This is the only case where you have to
  come back here and download the app again.

If GitHub can't be reached, Mate starts on the version it already has.

---

## Building it yourself

Both builds are the same shape: a Python environment holding Mate's own dependencies plus
[pywebview](https://pywebview.flowrey.dev/), packaged with PyInstaller, carrying a seed copy of
Mate so a fresh install works before it has ever reached the network.

```bash
git clone https://github.com/ProtossBlaster/leapmotor-mate.git ../leapmotor-mate
python3 -m venv buildenv
./buildenv/bin/python -m pip install \
    -r ../leapmotor-mate/poller/requirements.txt \
    -r ../leapmotor-mate/web/requirements.txt \
    pywebview pyinstaller
```

Then `./build_mac.sh && ./make_dmg.sh` on an Apple Silicon Mac, or
`powershell -ExecutionPolicy Bypass -File .\build_win.ps1` on 64-bit Windows (which also needs
[Inno Setup 6](https://jrsoftware.org/isinfo.php) for the installer:
`winget install --id JRSoftware.InnoSetup`).

The build **refuses to package an app certificate** if it finds one — see `.gitignore` and the
guard at the end of `build_win.ps1`.

`.github/workflows/build.yml` does all of the above on a tag, on native runners for each platform.

---

## License

AGPL-3.0, the same as Mate itself.
