**Install this one if you use a Mac.** Every macOS build before it reached people "damaged": macOS
refused to open it and offered no way round, so only a command in Terminal let it start
([#11](https://github.com/ProtossBlaster/MateDesktop/issues/11)). Windows is unchanged.

### macOS called the app damaged, and offered no "Open Anyway"

The app is signed ad hoc — Mate has no paid Apple certificate — and the build then wrote the shell's
version into the app's Info.plist. That file is part of what the signature seals, so every build up
to 1.2.1 left with a broken seal. macOS reads a broken seal as an app altered after signing: *"LeapMotor
Mate is damaged and can't be opened"*. An app it calls damaged never appears under Privacy & Security,
so the "Open Anyway" route the installer's own instructions describe could not work. Checked on the
published 1.2.1 disk image: `codesign --verify` answers *"invalid Info.plist (plist or signature have
been modified)"*, and Gatekeeper gives the same verdict.

The app is now signed again once it is complete, and the build stops if the signature does not
verify — checked a second time on the app inside the disk image, which is the file you download. A
downloaded copy of this build gets Gatekeeper's ordinary verdict for an app without a paid certificate:
the one that offers "Open Anyway".

### The first launch, as before

The app is still not signed with a paid Apple certificate, so the first launch still asks once:
macOS says it cannot check the app for malicious software — click **Done**, then **System Settings →
Privacy & Security → Open Anyway**.

### Already have a copy that says "damaged"?

Drag this one over it in Applications: your history and settings stay in
`~/Library/Application Support/LeapMotorMate`. To open the copy you have instead, run once in Terminal:
`xattr -dr com.apple.quarantine "/Applications/LeapMotor Mate.app"`

### Nothing else changes

The same Mate v4.7.18 inside the installer, the same Windows packages, nothing in the stored data.
