"""Keep the Python payload current, without ever re-signing the app.

The desktop build is split in two: a signed, notarised SHELL (this launcher + the Python
runtime + the compiled libraries) and a PAYLOAD (web/ + poller/, pure Python source). The
shell is what Apple notarises, and it only has to change when the dependency list changes —
6 times in 176 releases, last on 17 June 2026. The payload changes every release, and since
it is interpreted text rather than loadable machine code, swapping it needs no signature.

That split is what makes a daily release cadence survivable on the desktop: an update is a
~4 MB download of source we already publish, not an 80 MB re-notarised binary.

The payload is the source tarball GitHub generates for every tag by itself, so nothing about
the existing release process has to change to feed this.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

RELEASES_API = "https://api.github.com/repos/ProtossBlaster/leapmotor-mate/releases/latest"
TARBALL = "https://github.com/ProtossBlaster/leapmotor-mate/archive/refs/tags/{tag}.tar.gz"
PAYLOAD_PARTS = ("web", "poller")
_TIMEOUT = 30


def version_tuple(v: str) -> tuple:
    """'2.8.9' → (2, 8, 9). Unparseable parts sort lowest rather than raising."""
    out = []
    for part in str(v or "").lstrip("vV").split("."):
        m = re.match(r"\d+", part)
        out.append(int(m.group()) if m else 0)
    return tuple(out) or (0,)


def payload_version(payload_dir: Path) -> str | None:
    """The MATE_VERSION the installed payload declares (single source of truth, as in Docker)."""
    main = payload_dir / "web" / "main.py"
    if not main.is_file():
        return None
    for line in main.read_text(errors="replace").splitlines()[:80]:
        m = re.match(r'\s*MATE_VERSION\s*=\s*["\']([^"\']+)["\']', line)
        if m:
            return m.group(1)
    return None


def latest_release() -> dict | None:
    """The newest published release, or None when GitHub can't be reached (never fatal)."""
    try:
        req = urllib.request.Request(RELEASES_API, headers={
            "Accept": "application/vnd.github+json", "User-Agent": "leapmotor-mate-desktop"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.load(r)
        return {"tag": data.get("tag_name", ""), "version": str(data.get("tag_name", "")).lstrip("vV")}
    except Exception:
        return None


# ── the dependency guard ────────────────────────────────────────────────────────────────
# The one way this design can break: a release adds a library, the old shell doesn't carry it,
# and the payload lands anyway — leaving a desktop app that dies on import with no clue why.
# So before swapping anything, check that THIS interpreter can actually satisfy what the new
# payload asks for. If it can't, refuse the update and say so: a user on a slightly older
# version is a nuisance, a user with an app that won't start is a bug report.

_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*(==|>=|~=|>)?\s*([0-9][^\s;#]*)?")

# What a distribution is called on the index vs what you actually import. Only the pairs that
# don't follow the obvious rule need to be here.
_IMPORT_NAME = {
    "python-dotenv": "dotenv",
    "paho-mqtt": "paho.mqtt.client",
    "leapmotor-api": "leapmotor_api",
    "python-multipart": "multipart",
    "pillow": "PIL",
}


def _installed_version(dist: str) -> str | None:
    """Installed version, or None when the package metadata isn't readable."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version(dist)
        except PackageNotFoundError:
            return None
    except Exception:
        return None


def _is_importable(dist: str) -> bool:
    """Whether the library is actually usable, regardless of what the metadata says.

    A frozen build only carries distribution metadata for packages the build was told to
    collect whole, so `importlib.metadata` reports plenty of bundled libraries as missing.
    Trusting it alone made this guard block a perfectly runnable update over python-dotenv —
    a package the payload doesn't even import. What decides whether a payload can run is
    whether the import succeeds, so that is what gets asked.
    """
    import importlib.util
    candidates = [_IMPORT_NAME.get(dist.lower())] if dist.lower() in _IMPORT_NAME else []
    candidates += [dist, dist.replace("-", "_"), re.sub(r"^python[-_]", "", dist.replace("-", "_"))]
    for name in filter(None, candidates):
        try:
            if importlib.util.find_spec(name) is not None:
                return True
        except (ImportError, ValueError, ModuleNotFoundError):
            continue
    return False


def unsatisfied_requirements(payload_dir: Path) -> list[str]:
    """Requirements the running shell cannot meet — empty list means the payload is safe to run."""
    missing: list[str] = []
    for part in PAYLOAD_PARTS:
        req = payload_dir / part / "requirements.txt"
        if not req.is_file():
            continue
        for raw in req.read_text(errors="replace").splitlines():
            line = raw.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            m = _REQ_LINE.match(line)
            if not m:
                continue
            name, op, want = m.group(1), m.group(2), m.group(3)
            have = _installed_version(name)
            if have is None:
                # No metadata: fall back to the question that actually matters. Blocking an
                # update is a real cost to the user, so only do it when the library genuinely
                # cannot be imported — not merely when its paperwork is missing.
                if not _is_importable(name):
                    missing.append(f"{name} (not bundled in this app version)")
                continue
            # Only pin-style mismatches are worth blocking on; a newer bundled library than the
            # payload's floor is fine, which is the common case.
            if op in ("==", "~=") and want and version_tuple(have)[:len(version_tuple(want))] != version_tuple(want):
                missing.append(f"{name} {op}{want} (this app carries {have})")
            elif op in (">=", ">") and want and version_tuple(have) < version_tuple(want):
                missing.append(f"{name} {op}{want} (this app carries {have})")
    return missing


# ── download / install ──────────────────────────────────────────────────────────────────

def fetch_payload(tag: str, dest: Path, log=print) -> Path:
    """Download the release tarball and extract ONLY web/ + poller/ into `dest`."""
    url = TARBALL.format(tag=tag)
    log(f"downloading {url}")
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "src.tar.gz"
        req = urllib.request.Request(url, headers={"User-Agent": "leapmotor-mate-desktop"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r, open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
        log(f"got {archive.stat().st_size / 1e6:.1f} MB")
        with tarfile.open(archive) as tf:
            root = tf.getnames()[0].split("/")[0]
            wanted = [m for m in tf.getmembers()
                      if any(m.name.startswith(f"{root}/{p}/") for p in PAYLOAD_PARTS)]
            # Refuse anything that escapes the extraction root (tarball path traversal).
            for m in wanted:
                if os.path.isabs(m.name) or ".." in Path(m.name).parts:
                    raise ValueError(f"unsafe path in archive: {m.name}")
            tf.extractall(tmp, members=wanted)
        for part in PAYLOAD_PARTS:
            src = Path(tmp) / root / part
            if src.is_dir():
                shutil.copytree(src, dest / part, dirs_exist_ok=True)
    return dest


def payload_looks_complete(payload_dir: Path) -> str | None:
    """Reason this download is not a usable Mate, or None if it is.

    An archive can arrive intact and still be worthless: a tag published before the code landed,
    a repository reorganised, a proxy serving something else entirely. All of those extract
    without error and pass the dependency guard — which finds no requirements to check and
    therefore no objection. The empty payload then installs, the app fails to start, and only
    the rollback saves it. Cheaper to refuse it here: a download that doesn't contain the two
    entry points and a version number is not an update.
    """
    for part in PAYLOAD_PARTS:
        if not (payload_dir / part / "main.py").is_file():
            return f"{part}/main.py missing"
    if not payload_version(payload_dir):
        return "no MATE_VERSION found"
    return None


def install_payload(staged: Path, current: Path, previous: Path, log=print) -> None:
    """Swap staged → current, keeping the outgoing copy as the rollback target."""
    if previous.exists():
        shutil.rmtree(previous, ignore_errors=True)
    if current.exists():
        current.rename(previous)
    staged.rename(current)
    log(f"payload {payload_version(current)} installed (rollback kept at {previous.name})")


def rollback(current: Path, previous: Path, log=print) -> bool:
    """Put the previous payload back — used when a fresh one fails to come up."""
    if not previous.exists():
        return False
    broken = current.with_name("payload_broken")
    shutil.rmtree(broken, ignore_errors=True)
    if current.exists():
        current.rename(broken)
    previous.rename(current)
    shutil.rmtree(broken, ignore_errors=True)
    log(f"rolled back to {payload_version(current)}")
    return True
