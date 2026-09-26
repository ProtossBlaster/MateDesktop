# Changelog

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
