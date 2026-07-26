#!/bin/bash
# Wrap the built app into the disk image people actually download.
#
# A .app is a folder. Handed over as-is it arrives as a zip that expands into "something" in
# Downloads, and the app then runs from wherever it happened to land — which is also where an
# unsigned app is most likely to be quarantined. A disk image is the convention the audience for
# this build already knows: open it, drag the icon onto Applications, done.
#
# Deliberately plain: two icons and a text file, no custom background, no window layout. A laid-out
# DMG has to be scripted through the Finder, which means asking for Automation permission on the
# BUILD machine and a fragile dance of AppleScript — for a window whose whole message is "drag left
# onto right". If it ever earns a background, that is a design job, not a packaging one.
#
# The instructions ride INSIDE the image on purpose. The one thing that will stop a first-time user
# is macOS refusing to open an unsigned app, and at that moment they are looking at this window,
# not at a GitHub release page.
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/dist/LeapMotor Mate.app"
STAGING="$HERE/build/dmg"
OUT_DIR="$HERE/dist"

[ -d "$APP" ] || { echo "no app to package — run ./build_mac.sh first"; exit 1; }

VERSION="$(/usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" "$APP/Contents/Info.plist")"
ARCH="$(lipo -archs "$APP/Contents/MacOS/LeapMotor Mate" | tr ' ' '-')"
DMG="$OUT_DIR/LeapMotor-Mate-$VERSION-$ARCH.dmg"

echo "==> staging"
rm -rf "$STAGING" "$DMG"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

cat > "$STAGING/First launch — read me.txt" <<'TXT'
LeapMotor Mate for macOS
========================

1. Drag "LeapMotor Mate" onto the Applications folder in this window.

2. Open it. macOS will refuse the first time, saying the app cannot be checked
   for malicious software. That is expected: this app is not signed with an
   Apple Developer certificate (that is a paid subscription, and Mate is free).

   To allow it:
     - Open System Settings > Privacy & Security
     - Scroll down to Security. There is a line about "LeapMotor Mate"
       being blocked, with an "Open Anyway" button next to it.
     - Click Open Anyway, then confirm.

   You only ever do this once.

   NB: right-clicking the app and choosing Open no longer works on current
   macOS versions. Use System Settings, as above.

3. Mate asks for the Leapmotor app certificate: two files, app.crt and
   app.key. They are the same for everybody — nothing to do with your
   account — and the setup screen links straight to where they live:

       https://github.com/markoceri/leapmotor-certs

   Download both, then drag them into the two boxes. Once only; Mate keeps
   them from then on. (Mate does not ship them itself: they are somebody
   else's to give out, and a copy frozen into an app goes stale the day
   they change it.)

4. Sign in with a Leapmotor account that Mate has to ITSELF.

   NOT the account you use on the official phone app. Leapmotor allows about
   one active session per account: a second client fights Mate for it, they
   evict each other in a loop, and the car goes offline to Mate with gaps in
   the history and no error to explain them.

   Add a second account to the car in the official app, and give Mate that
   one. You will also need the operation PIN — the one the app asks for to
   authorise remote commands.

Good to know
------------
* This build runs on Apple Silicon Macs only (M1 and later). It will not
  open on an Intel Mac.

* Mate records only while the app is open. Anything the car does after you
  close it is not saved, and cannot be filled in afterwards — the cloud keeps
  no history to replay. There is a "Start at login" switch in Settings if you
  would rather not have to remember.

* Your data lives in:
      ~/Library/Application Support/LeapMotorMate
  It stays there when you move, replace or delete the app.

* Mate updates itself. Each time you open it, it fetches the newest version
  and starts on it — you do not need to download this file again.

Project, source and issues:
  https://github.com/ProtossBlaster/leapmotor-mate
TXT

echo "==> building the disk image"
hdiutil create \
  -volname "LeapMotor Mate" \
  -srcfolder "$STAGING" \
  -fs HFS+ \
  -format UDZO \
  -ov \
  "$DMG" >/dev/null

rm -rf "$STAGING"
echo "==> done: $DMG"
du -h "$DMG" | cut -f1 | sed 's/^/    /'
