#!/usr/bin/env python3
"""Load ZizkaDB history exported by the GitHub Action into a local ZizkaDB.

Usage (after the quickstart is running):
    python3 open_in_dashboard.py *.ndjson

Env: ZIZKADB_HOST (default http://localhost:8000), ZIZKADB_DASHBOARD_URL,
     ZIZKADB_API_KEY (default zizkadb_dev_local, the quickstart's local key).
Standard library only.
"""

import json
import os
import sys
import urllib.request
import webbrowser

HOST = os.environ.get("ZIZKADB_HOST", "http://localhost:8000").rstrip("/")
KEY = os.environ.get("ZIZKADB_API_KEY", "zizkadb_dev_local")
BATCH = 1000


def post(events):
    req = urllib.request.Request(
        f"{HOST}/v1/events/import",
        data=json.dumps({"events": events}).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main(paths):
    if not paths:
        sys.exit(__doc__)
    agent = None
    for path in paths:
        with open(path, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        for i in range(0, len(lines), BATCH):
            result = post(lines[i:i + BATCH])
            print(f"{path}: imported {result.get('imported', 0)}, "
                  f"duplicates {result.get('duplicates', 0)}, failed {result.get('failed', 0)}")
        if lines:
            agent = lines[0].get("agent", agent)
    dash = os.environ.get("ZIZKADB_DASHBOARD_URL") or (
        HOST[:-5] + ":3001" if HOST.endswith(":8000") else HOST)
    url = dash.rstrip("/") + "/dashboard/activity" + (f"?agent={agent}" if agent else "")
    print(f"\nOpen: {url}  (click an event, then 'Why? (causal)')")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print("ZizkaDB is open source: https://github.com/ZIZKA-AI-SL/ZizkaDB")


if __name__ == "__main__":
    main(sys.argv[1:])
