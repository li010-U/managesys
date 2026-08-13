# -*- coding: utf-8 -*-
"""自动备份入口（供计划任务/守护调用）。
用法:
    python scripts/auto_backup.py [--keep N] [--dir <backup_dir>] [--log <logfile>]

接口约定：成功返回码 0，失败返回非 0	extamp;
并在日志中写入结果，方便计划任务回看 / 告警。
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


def main() -> int:
    ap = argparse.ArgumentParser(description="auto backup")
    ap.add_argument("--keep", type=int, default=30)
    ap.add_argument("--dir", default=str(ROOT / "backups"))
    ap.add_argument("--log", default=str(ROOT / "backups" / "auto_backup.log"))
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    logging.basicConfig(
        filename=args.log, level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s",
    )

    import backup_utils
    try:
        path = backup_utils.backup(target_dir=args.dir, keep=args.keep)
        logging.info("BACKUP OK %s", path)
        print(f"[OK] {path}")
        return 0
    except Exception as e:
        logging.error("BACKUP FAILED: %s", e)
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
