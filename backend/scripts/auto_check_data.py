"""Auto data-consistency check entrypoint (scheduled task / guardian).

Usage:
    python scripts/auto_check_data.py [--fix] [--log <file>]

Contract: exit code 0 on no errors, nonzero when errors are found; logs the
summary so the scheduled task can page/alert. Honours DATABASE_URL like the app.
"""
from __future__ import annotations
import argparse
import datetime
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # backend/
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser(description="auto check-data")
    ap.add_argument("--fix", action="store_true", help="apply safe fixes (recompute available_units, orphan ip refs)")
    ap.add_argument("--log", default=str(ROOT / "data" / "auto_check_data.log"), help="log file")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    logging.basicConfig(
        filename=args.log, level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s",
    )

    import data_audit
    try:
        report = data_audit.run_audit()
        s = report["summary"]
        info = report.get("info_counts", {})
        msg = (
            "CHECK ok=%s warn=%s error=%s unmounted=%s db=%s"
            % (s["ok"], s["warn"], s["error"], info.get("unmounted_devices", 0), report["db"])
        )
        if args.fix:
            fixed = data_audit.apply_fixes()
            msg += " fixed=%s" % fixed
        if s["error"]:
            logging.error("CHECK FAILED " + msg)
            print("[FAILED]", msg)
            return 1
        logging.info("CHECK OK " + msg)
        print("[OK]", msg)
        return 0
    except Exception as e:
        logging.error("CHECK ERROR %s", e)
        print("[ERROR]", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
