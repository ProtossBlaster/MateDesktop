# Changelog

## 1.2.2

- macOS no longer calls the app damaged. Every macOS build up to 1.2.1 wrote the shell version into
  Info.plist after PyInstaller had signed the bundle, which broke the seal: a downloaded copy was
  "damaged and can't be opened", with no "Open Anyway" in Privacy & Security, and only removing the
  quarantine by hand in Terminal let it start (#11). The bundle is signed again once it is final,
  and the build stops if the signature does not verify — make_dmg.sh checks the app once more
  inside the disk image, which is the file people download.

Nothing else changes: the same Mate v4.7.18 inside the installer, the same Windows packages, and
nothing in the stored data.

## 1.2.1

- The app can reach GitHub again: a frozen build looked for the machine's certificate authorities
  at a path that exists only on the build machine, so every update check failed verification and
  the log said "GitHub unreachable". The shell now verifies against the bundle it already hands
  its children, and a failed check says what actually went wrong.
- certifi is a build requirement in its own right. It used to arrive as a dependency of the cloud
  library 1.2.0 removed, and left with it: 1.2.0 shipped with no trust store at all. Both build
  scripts now refuse to produce a package missing anything they bundle.
- Installing a newer app over an older one replaces a payload older than the one inside the
  installer, instead of starting it. A 1.2.0 installed over an install stuck on Mate 2.10.1 could
  not run that payload — the library it imports is gone — and exited without drawing anything.
- When the services never come up, the app says so on screen and names the log file.

Nothing changes in the stored data. An install that had been stuck on an old Mate moves to the
payload inside this installer at the first launch, and to the newest release at the second.

## 1.2.0

- New installer builds start from the released Mate 4.7.8 payload.
- The shell no longer carries a second cloud library: since Mate 4.7.7 the payload runs on Mate's
  own client alone, so the build bundles only what that payload imports.
- The Leapmotor app certificate travels inside the payload and Mate installs it at the first start:
  the first-run check expects the material ready and a wizard that asks only for the account, and
  the packaging guards still refuse any other copy of a certificate.
- Existing Desktop users receive Mate 4.7.7 through the normal payload update; upgrading the shell
  is optional. A 1.2.0 shell does not roll a payload back below 4.7.7: those ask for the old
  library, and the dependency guard refuses them instead of starting them.


## 1.1.0

- Default new installer builds to the released Mate 4.0.0 payload.
- Verify Mate 4 against the actual released Desktop 1.0 binaries on native macOS
  and Windows, including migration worker startup and legacy compatibility selection.
- Existing Desktop 1.0 users receive Mate 4 through the normal payload update;
  upgrading the shell is optional.
- Preserve the legacy API for accounts that cannot yet qualify for the independent
  API and for payload rollback. Existing account settings and history remain in place.


## 1.1.0-rc.1

The shell and installer metadata use numeric version **1.1.0**. This candidate
supports the **Mate 4.0.0-rc.1** payload, whose independent API is **0.1.0a8**.

- Explicit `--payload-tag` selection supports release candidates while automatic
  payload updates continue to select stable releases.
- Bundle the additional standard library/native-lock dependencies needed by the
  independent API and recognize vendored payload packages in contract checks.
- Retain the legacy API in shell build dependencies for 3.x payload rollback.
- Test both service entry points and the actual frozen executables in native CI.
- Mark hyphenated shell release tags as prereleases in the draft-release workflow.

Payload rollback restores application code. Preserve the complete data directory
before trying the migration; see the candidate release notes for recovery limits.
