"""The shell's own HTTPS, which in every released build so far trusted nothing at all.

A frozen build carries its own OpenSSL, and that OpenSSL looks for the machine's certificate
authorities at the path it was compiled with — on these builds inside the python.org framework,
which exists on the build machine and on no user's Mac. `ssl.create_default_context()` therefore
loaded ZERO authorities and every request the launcher made to GitHub failed verification. The
exception was swallowed and the log said "GitHub unreachable" on a machine whose network was fine,
so the payload never moved off the version the installer seeded (MateDesktop #10: a 1.0.0 install
still on Mate 2.10.1 three months later, with the app's own badge offering 4.7.17 — the PAYLOAD
has a trust store, because the launcher hands its children one).

Measured on the released 1.0.0 and 1.2.0 bundles: 0 certificates, CERTIFICATE_VERIFY_FAILED.

    python3 -m pytest test_the_update_check_trusts_github.py
"""
import io
import json
import ssl
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "mate_desktop"))
import updater


def _tarball(version: str = "4.7.18") -> io.BytesIO:
    """The shape of the archive GitHub serves for a tag: everything under one root directory."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tf:
        for part in ("web", "poller"):
            body = f'MATE_VERSION = "{version}"\n'.encode()
            info = tarfile.TarInfo(f"leapmotor-mate-{version}/{part}/main.py")
            info.size = len(body)
            tf.addfile(info, io.BytesIO(body))
    raw.seek(0)
    return raw


def test_the_build_carries_a_certificate_bundle():
    """Without this the app ships with no trust store and never updates itself again."""
    assert updater.ca_bundle(), "certifi is missing from this environment"


def test_the_bundle_is_the_one_the_requests_verify_against():
    context = updater.https_context()
    assert context.get_ca_certs(), "the shell would talk to GitHub trusting nothing"


def test_the_release_lookup_verifies_against_it(monkeypatch):
    seen = {}

    def urlopen(request, **kwargs):
        seen.update(kwargs)
        return io.BytesIO(json.dumps({"tag_name": "v4.7.18"}).encode())

    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    assert updater.latest_release()["version"] == "4.7.18"
    assert isinstance(seen.get("context"), ssl.SSLContext)
    assert seen["context"].get_ca_certs()


def test_the_download_verifies_against_it(monkeypatch, tmp_path):
    seen = {}

    def urlopen(request, **kwargs):
        seen.update(kwargs)
        return _tarball()

    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    updater.fetch_payload("v4.7.18", tmp_path / "staged", log=lambda _: None)
    assert updater.payload_version(tmp_path / "staged") == "4.7.18"
    assert isinstance(seen.get("context"), ssl.SSLContext)
    assert seen["context"].get_ca_certs()


def test_a_check_that_failed_says_what_went_wrong(monkeypatch):
    """"GitHub unreachable" is what a verification failure looked like for three releases."""
    def urlopen(request, **kwargs):
        raise ssl.SSLCertVerificationError("certificate verify failed: unable to get local issuer")

    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    updater.last_error = ""
    assert updater.latest_release() is None
    assert "certificate verify failed" in updater.last_error


def test_a_check_that_worked_leaves_no_stale_reason(monkeypatch):
    updater.last_error = "something from before"
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda request, **kw: io.BytesIO(json.dumps({"tag_name": "v4.7.18"}).encode()))
    assert updater.latest_release()
    assert updater.last_error == ""
