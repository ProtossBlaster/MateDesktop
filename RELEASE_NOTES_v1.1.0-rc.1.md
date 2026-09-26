# MateDesktop v1.1.0-rc.1

This is an opt-in shell prerelease for testing the independent API migration.
It is not a stable release.

| Component | Version |
| --- | --- |
| Desktop shell / numeric installer metadata | 1.1.0 |
| Desktop GitHub prerelease tag | v1.1.0-rc.1 |
| Intended Mate seed / payload | 4.0.0-rc.1 |
| Vendored independent API | 0.1.0a8 |

The shell supplies Python, native dependencies, and the launcher. Mate's `web/`
and `poller/` remain a separately updated payload; `leapmotor_cloud` travels inside
that payload. Check the attached `payload-seed.txt` for the actual seed used by
these installers.

## Opt in

Stop every other Mate instance using the same cloud account. Back up the complete
Desktop data directory, including database, `secret.key`, certificates, and any
private account material. For an isolated test, set `MATE_APP_DIR` to a disposable
directory before launching the executable.

A shell seeded with Mate 4.0.0-rc.1 starts on that candidate. On another compatible
seed, explicitly request `--payload-tag v4.0.0-rc.1`. Automatic updates continue
checking stable releases only; they do not opt existing stable users into an RC.

The updater keeps the outgoing payload and restores it if the new web service
fails startup. This restores code, not the database. Mate also creates its own
one-time migration backup before non-demo startup. Keep the complete pre-test
backup for recovery; never assume a newer database can be used by old code.
Candidate-only history is not automatically merged into an older backup.

## Build and validation

Both platforms use `requirements-shell.txt` together with the selected Mate
payload requirements. The legacy `leapmotor-api` dependency remains bundled so
an older payload can still run after rollback. Candidate API code is vendored in
the payload and is not installed from PyPI by the shell build.

Native CI runs startup checks against the built macOS and Windows executables.
The publisher must verify the final candidate commit's CI results and seed before
publishing. Successful startup does not establish live cloud, vehicle-command,
sleep/recovery, or installer-upgrade behavior on a user's machine.

The packages remain unsigned. Use the release's `SHA256SUMS` and provenance
artifacts to check downloads; checksum matching alone does not establish signer
identity. No signing or notarization is introduced by this candidate.
