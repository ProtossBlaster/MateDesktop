# MateDesktop v1.1.0

MateDesktop 1.1.0 ships with the Mate 4.0.0 payload. The shell and payload have
independent version numbers; `payload-seed.txt` records the installer seed.

## Existing installations

**Desktop 1.0 already supports the Mate 4 update.** Open Mate as usual and its
normal updater fetches the stable payload. There is no shell reinstall,
certificate upload, account setup, database export/import or migration command.
Desktop 1.1.0 remains an optional shell update for existing users.

Mate preserves account settings, the encryption key, certificates and history.
Before changing API backend it creates a private backup and qualifies a staged
copy with bounded sign-in and read-only vehicle checks. Qualification failure,
an unsupported model, or a REEV/mixed-model account outside the new API's
coverage automatically keeps the legacy compatibility backend for the whole
account. Vehicle commands never trigger fallback or get replayed through a
second API. This retains existing functionality; it does not add new REEV support.

The updater also keeps its existing code rollback when a new payload cannot
start. Code rollback and the separate migration data backup serve different
purposes; the updater does not replace the database with an older snapshot.

## New installations and packaging

Use the macOS Apple Silicon or Windows x64 package for a new installation and
complete the usual first-run setup. Both packages carry the runtime, native
libraries and the legacy compatibility API. The independent API ships inside
Mate's payload.

Builds default to the explicit `v4.0.0` Mate seed. Native compatibility checks
exercise the actual released Desktop 1.0 binaries as well as checks against newly
built executables. Frozen startup checks do not establish every live vehicle
command or sleep/recovery scenario.

The packages remain unsigned. The release includes `SHA256SUMS` and build
provenance; checksum matching verifies download integrity, not signer identity.
