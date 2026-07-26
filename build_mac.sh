#!/bin/bash
# Build LeapMotor Mate.app for macOS.
#
# The bundle carries the SHELL only: the Python runtime, the compiled libraries, and a seed
# copy of the payload so a fresh install works before it has ever reached the network. Every
# release after that arrives as source over the updater, which is why this build — and the
# notarisation that would go with it — is needed only when the dependency list changes.
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${MATE_REPO:-$HOME/leapmotor-mate}"
BUILD_PY="$HERE/buildenv/bin/python"
OUT="$HERE/dist"

[ -x "$BUILD_PY" ] || { echo "build venv missing — see the prototype notes"; exit 1; }
[ -d "$REPO/web" ] || { echo "Mate source not found at $REPO"; exit 1; }

echo "==> staging the seed payload from $REPO"
rm -rf "$HERE/payload_seed"
mkdir -p "$HERE/payload_seed"
for part in web poller; do
  # Ship what the app runs, and nothing else: no caches, no test fixtures.
  rsync -a --exclude '__pycache__' --exclude '*.pyc' "$REPO/$part" "$HERE/payload_seed/"
done
# NB: the app certificate is deliberately NOT bundled — see the note by --add-data below.
echo "    payload $(grep -m1 'MATE_VERSION' "$HERE/payload_seed/web/main.py" | cut -d'"' -f2)"

echo "==> building the app bundle"
rm -rf "$OUT" "$HERE/build"
"$BUILD_PY" -m PyInstaller \
  --name "LeapMotor Mate" \
  --windowed \
  --icon "$HERE/Mate.icns" \
  `# Reverse-DNS, as macOS expects: it is what the OS keys preferences, permissions and the` \
  `# login item on, and what code signing requires. The PyInstaller default ("LeapMotor Mate")` \
  `# is not a valid identifier and would have had to change before the first signed build.` \
  --osx-bundle-identifier "$(grep -m1 '^BUNDLE_ID' "$HERE/mate_desktop/plat_mac.py" | cut -d'"' -f2)" \
  --noconfirm \
  --distpath "$OUT" \
  --workpath "$HERE/build" \
  --specpath "$HERE/build" \
  --add-data "$HERE/payload_seed:payload_seed" \
  `# NO certs/ here, and it is not an omission. app.crt/app.key are NOT Mate's to redistribute:` \
  `# they are the Leapmotor APP's TLS certificate — the same one for every user, not anybody's` \
  `# account — published at markoceri/leapmotor-certs, and the setup wizard asks the user to` \
  `# upload them once on first run, exactly as under Docker and Home Assistant. Bundling the` \
  `# build machine's copy would make this the one channel that hands out a third party's` \
  `# certificate and private key on Mate's behalf, and would freeze every install onto whatever` \
  `# copy happened to be on this disk that day — invisible the moment it is rotated.` \
  `# Caught before publishing, by Silvio asking the right question about API keys.` \
  `# Collect these WHOLE, not just what static analysis can reach.` \
  `# The payload is downloaded after the build, so nothing it imports is visible here — and` \
  `# importing a package root does not pull in its submodules (cryptography.fernet was the` \
  `# second failure of this prototype, right after sqlite3). Bundling entire libraries is the` \
  `# only thing that survives a payload the build has never seen.` \
  --collect-all webview \
  --collect-all uvicorn \
  --collect-all fastapi \
  --collect-all leapmotor_api \
  --collect-all cryptography \
  --collect-all paho \
  --collect-all jinja2 \
  --collect-all PIL \
  --collect-all multipart \
  --collect-all certifi \
  --collect-all tzdata \
  --collect-submodules sqlite3 \
  "$HERE/mate_desktop/launcher.py"

# The version has to be IN the bundle, not just in the launcher: it is what Get Info shows, what
# Finder compares when replacing an older copy, and what a signed build would be stamped with.
# PyInstaller leaves it at 0.0.0, so it is read from the one place that defines it and written in.
SHELL_VERSION="$(grep -m1 '^SHELL_VERSION' "$HERE/mate_desktop/launcher.py" | cut -d'"' -f2)"
PLIST="$OUT/LeapMotor Mate.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $SHELL_VERSION" "$PLIST"
# CFBundleVersion (the build number Finder compares) isn't in PyInstaller's plist at all, so it
# has to be Added rather than Set — Set on a missing key fails.
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $SHELL_VERSION" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $SHELL_VERSION" "$PLIST"

echo "==> done: $OUT/LeapMotor Mate.app (shell $SHELL_VERSION)"
du -sh "$OUT/LeapMotor Mate.app"
