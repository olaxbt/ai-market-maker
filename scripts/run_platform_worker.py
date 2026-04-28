#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from api.copy_routes import execute_inbox_item  # noqa: E402
from storage.leadpage_db import (  # noqa: E402
    auto_execute_targets,
    database_url,
    fanout_new_signals,
    insert_local_backtest_result_if_missing,
    unread_ops_inbox,
)


def main() -> None:
    if not database_url():
        raise SystemExit("DATABASE_URL is not set (worker requires Postgres mode).")

    interval = float((os.getenv("PLATFORM_WORKER_INTERVAL_SEC") or "2.0").strip() or "2.0")
    interval = max(0.5, min(30.0, interval))
    sync_local = (os.getenv("PLATFORM_SYNC_LOCAL_BACKTESTS") or "").strip() in {"1", "true", "TRUE"}
    sync_every = float(
        (os.getenv("PLATFORM_SYNC_LOCAL_BACKTESTS_EVERY_SEC") or "10").strip() or "10"
    )
    sync_every = max(2.0, min(300.0, sync_every))

    cursor = (os.getenv("PLATFORM_WORKER_CURSOR") or "default").strip() or "default"
    batch = int((os.getenv("PLATFORM_WORKER_BATCH") or "200").strip() or "200")
    batch = max(10, min(2000, batch))

    print(
        f"[worker] start cursor={cursor} interval={interval}s batch={batch} sync_local_backtests={sync_local}"
    )
    last_sync = 0.0
    while True:
        try:
            now = time.time()
            if sync_local and (now - last_sync) >= sync_every:
                inserted = 0
                runs_dir = _ROOT / ".runs" / "backtests"
                if runs_dir.is_dir():
                    for p in sorted(runs_dir.iterdir(), reverse=True)[:200]:
                        if not p.is_dir():
                            continue
                        summary_path = p / "summary.json"
                        if not summary_path.is_file():
                            continue
                        try:
                            obj = json.loads(summary_path.read_text(encoding="utf-8"))
                        except Exception:
                            continue
                        if isinstance(obj, dict) and insert_local_backtest_result_if_missing(
                            summary=obj
                        ):
                            inserted += 1
                if inserted:
                    print(f"[worker] synced local backtests inserted={inserted}")
                last_sync = now

            out = fanout_new_signals(cursor_name=cursor, limit=batch)
            processed = int(out.get("processed") or 0)
            inserted = int(out.get("inserted") or 0)
            last_id = int(out.get("last_signal_id") or 0)
            if processed or inserted:
                print(
                    f"[worker] processed={processed} inserted={inserted} last_signal_id={last_id}"
                )

            # Auto-execute (safe-by-default): only for (user,provider) with enabled+auto_execute.
            if (os.getenv("PLATFORM_WORKER_AUTO_EXECUTE") or "").strip() in {"1", "true", "TRUE"}:
                for uid, prov in auto_execute_targets(limit=500):
                    ops = unread_ops_inbox(uid, prov, limit=3)
                    for item in ops:
                        inbox_id = int(item["id"])
                        try:
                            res = execute_inbox_item(user_id=uid, inbox_id=inbox_id)
                            if res.get("ok") is True:
                                print(
                                    f"[worker] auto-executed user={uid} provider={prov} inbox_id={inbox_id}"
                                )
                            else:
                                print(
                                    f"[worker] auto-exec rejected user={uid} provider={prov} inbox_id={inbox_id}"
                                )
                        except Exception as e:
                            print(
                                f"[worker] auto-exec error user={uid} provider={prov} inbox_id={inbox_id}: {e}"
                            )
        except KeyboardInterrupt:
            print("[worker] stopping")
            return
        except Exception as e:
            print(f"[worker] error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
