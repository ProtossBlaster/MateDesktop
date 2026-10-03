# MateDesktop v1.2.1

MateDesktop 1.2.1 ships with the Mate 4.7.18 payload. The shell and payload have independent
version numbers; `payload-seed.txt` records the installer seed.

**This one is not optional.** Every build before it could not check for a Mate release at all on a
machine that did not happen to carry a particular certificate file, so the payload stayed on
whatever the installer seeded — for as long as the app was installed.

## The app could not reach GitHub, and said the network was at fault

A frozen build carries its own OpenSSL, and that OpenSSL looks for the machine's certificate
authorities at the path it was compiled with: inside the python.org framework, which exists on the
build machine and on no user's Mac. `ssl.create_default_context()` therefore loaded **zero**
authorities, every request the launcher made to GitHub failed verification, and the log said
"update check skipped (GitHub unreachable)".

Mate itself never had the problem — the launcher hands the two services a certificate bundle — so
the version badge could announce a release the app would never install. That is what
[#10](https://github.com/ProtossBlaster/MateDesktop/issues/10) looked like from the user's side: a
1.0.0 install still running the Mate 2.10.1 its installer seeded in July, with an amber badge
offering 4.7.17 on every launch.

Measured on the released 1.0.0 and 1.2.0 bundles: 0 certificates loaded,
`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. With the fix, the same
machine with no system trust store at all reaches GitHub and installs the newest release.

The shell now verifies against the same bundle it gives the payload, and a check that failed says
what failed instead of blaming the network.

## 1.2.0 had no trust store at all

certifi had only ever arrived as a dependency of the cloud library 1.2.0 removed, and left with it.
`--collect-all certifi` on a package that is not installed is a warning PyInstaller writes to a log
nobody reads, so the build succeeded and the package shipped without it — which also left the
payload without a bundle for everything it fetches outside the Leapmotor cloud (that one pins its
own certificate and kept working). certifi is now a build requirement in its own right, and both
build scripts refuse to produce a package missing anything they bundle.

## A newer app no longer starts a payload it cannot run

The payload lives in the data directory and outlives the app. Until now the seed inside the
installer was used only when there was no payload at all, so 1.2.0 installed over an install stuck
on Mate 2.10.1 ran that 2.10.1 — and 1.2.0 no longer carries the library it imports. Both services
died on `ModuleNotFoundError: No module named 'leapmotor_api'`, the port never opened, and the app
exited without drawing anything: "even if I install version 1.2.0 over it, the app no longer
launches".

The seed is now the floor the shell guarantees: a payload older than it, or one too damaged to name
its version, is replaced by it at launch. A payload newer than the seed — the normal case — is left
alone. The database, the settings and the history are untouched.

And when the services never come up for any reason, the app now says so on screen and names the log
file, instead of vanishing.

## Existing installations

Open the app once: it moves to the Mate payload inside this installer, then to the newest release
at the next launch. Nothing to export, import or set up again.

Anyone who cannot install this build and wants their Mate up to date meanwhile can close the app,
delete the folder `payload` inside `~/Library/Application Support/LeapMotorMate` (Windows:
`%LOCALAPPDATA%\LeapMotorMate`) and reopen it. The data lives beside that folder and is not
affected.

## New installations and packaging

Builds are made on native runners (macOS on Apple Silicon, Windows x64) from the released Mate
4.7.18 tag. The packages are not signed; checksums are published with the release.

## Verification

- 51 shell unit tests, 14 of them new: 9 failed against 1.2.0 and pass here.
- Measured on this Mac with the released 1.0.0 and 1.2.0 bundles and with the 1.2.1 build: the
  release lookup with the system trust store made unavailable (`None` before, `v4.7.18` now), and a
  data directory left on Mate 2.10.1 opened by each shell (no window before, Mate 4.7.18 serving
  now).
