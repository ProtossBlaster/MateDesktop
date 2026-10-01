# MateDesktop v1.2.0

MateDesktop 1.2.0 ships with the Mate 4.7.8 payload. The shell and payload have independent version
numbers; `payload-seed.txt` records the installer seed.

## Existing installations

**Desktop 1.0 and 1.1 already receive Mate 4.7.8.** Open Mate as usual and its normal updater
fetches the stable payload: no reinstall, no certificate, no account setup. Desktop 1.2.0 is an
optional shell update.

## What changes in the shell

- **One cloud client.** Mate 4.7.7 runs on its own cloud client alone, so the shell no longer
  bundles the third-party library earlier payloads could fall back on.
- **Nothing to download at first run.** The Leapmotor app certificate travels inside the payload
  and Mate installs it itself; the setup wizard asks only for the Leapmotor account. The packaging
  checks still refuse any other copy of a certificate in the build.
- **Rollback floor.** The updater's code rollback keeps working for 4.7.7 and later. A payload older
  than 4.7.7 asks for the old library, which this shell no longer carries: the dependency guard
  refuses it rather than start an app that would fail on an import.

## New installations and packaging

Builds are made on native runners (macOS on Apple Silicon, Windows x64) from the released Mate
4.7.8 tag. The packages are not signed; checksums are published with the release.
