dev_tools/ -- developer-only scripts
=======================================

These scripts are moved here from the backend/root so they do NOT sit in the
production import/runtime path. They are ONE-OFF demo, scratch, or backfill
tools that write directly to the database (raw sqlite3 or HTTP to localhost)
and can corrupt production data if run carelessly.

SAFETY GUARD
------------
Most of these scripts start with:

    import _guard
    _guard.ensure_dev_mode()

When run, they refuse to continue unless the environment variable
`ALLOW_DEV_TOOL_WRITE` is set to `1`, e.g.:

    # Windows PowerShell:
    $env:ALLOW_DEV_TOOL_WRITE="1"; python dev_tools/add_racks.py
    # bash/zsh:
    ALLOW_DEV_TOOL_WRITE=1 python dev_tools/add_racks.py

Keep `ALLOW_DEV_TOOL_WRITE` unset in normal operation and NEVER point these at
a shared/pre-production database.

To regenerate demo data through the API instead, prefer the application's own
APIs/init rather than these raw-write scripts.

Note: scripts marked with a leading underscore (`_*.py`) are scratch/abandoned
and are kept only for reference.
