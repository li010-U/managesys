# -*- coding: utf-8 -*-
"""一键解决全部历史告警（批量置为「已解决」）。

把当前所有 new/acknowledged 状态的告警批量标记为 resolved，并：
  - 回填 resolved_at（当前时间）。
  - 回填 duration_seconds（按 created_at 到 resolved_at）。
  - 回填 lifecycle_action='batch_resolve'。
  - 回填 cooldown_until（resolved_at + cooldown 分钟，避免立即重复刷屏）。

用法:
  ALLOW_DEV_TOOL_WRITE=1 python resolve_all_alerts.py --cooldown 5
"""
import _guard
import argparse
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parents[1] / 'data' / 'managesys.db')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cooldown', type=int, default=5, help='resolved 后冷却分钟数(默认5, 避免立即重告警)')
    parser.add_argument('--dry-run', action='store_true', help='只统计不写库')
    args = parser.parse_args()
    _guard.ensure_dev_mode()

    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    now = datetime.now()

    stats = c.execute("SELECT status, COUNT(*) FROM alerts WHERE status IN ('new','acknowledged') GROUP BY status").fetchall()
    total = sum(n for _, n in stats)

    if args.dry_run:
        print('待处理告警: %d 条 %s' % (total, stats))
        print('--dry-run，未做任何修改。')
        return

    # resolved_at 统一用当前时间；cooldown_until 错开少量避免瞬间全部到期
    resolved_at = now.strftime('%Y-%m-%d %H:%M:%S.%f')
    cooldown_until = (now + timedelta(minutes=args.cooldown)).strftime('%Y-%m-%d %H:%M:%S.%f')

    cur = c.execute(
        """UPDATE alerts
           SET status='resolved',
               resolved_at=?,
               lifecycle_action='batch_resolve',
               cooldown_until=?,
               duration_seconds=CASE
                   WHEN created_at IS NOT NULL THEN
                       CAST((julianday(?) - julianday(created_at)) * 86400 AS INTEGER)
                   ELSE duration_seconds
               END
           WHERE status IN ('new','acknowledged')""",
        (resolved_at, cooldown_until, resolved_at),
    )
    conn.commit()
    affected = cur.rowcount
    print('已解决告警: %d 条' % affected)
    after = c.execute("SELECT status, COUNT(*) FROM alerts GROUP BY status").fetchall()
    print('处理后状态分布:', after)
    conn.close()


if __name__ == '__main__':
    main()
