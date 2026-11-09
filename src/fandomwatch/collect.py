"""Scheduled comment collection. Config (JSON): {"titles": [{"name": "X", "videos": {"trailer": ["<youtube id>"]}}]}"""
import json
import time

from .ingest import QuotaExceeded, ingest_youtube_comments


def load_config(path):
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    for t in cfg.get("titles", []):
        if not t.get("name") or not isinstance(t.get("videos"), dict) or not t["videos"]:
            raise ValueError(f"bad title entry (needs name + videos map): {t}")
    return cfg


def collect_once(conn, client, config, pages=2):
    """First video of each title; one bad title never stops the run. Quota exhaustion does."""
    s = {"titles": 0, "comments": 0, "errors": []}
    for t in config["titles"]:
        try:
            s["comments"] += ingest_youtube_comments(conn, client, t["name"], next(iter(t["videos"].values()))[0], pages)
            s["titles"] += 1
        except QuotaExceeded:
            raise
        except Exception as exc:
            s["errors"].append(f"{t['name']}: {exc}")
    return s


def schedule(conn, client, config, every_s, max_runs=None, sleep=time.sleep, log=print):
    runs = 0
    while max_runs is None or runs < max_runs:
        try:
            s = collect_once(conn, client, config)
            log(f"run {runs + 1}: {s['comments']} comments, {len(s['errors'])} errors, quota {client.used}")
        except QuotaExceeded as exc:
            log(f"quota exhausted, stopping: {exc}")
            return runs
        runs += 1
        if max_runs is None or runs < max_runs:
            sleep(every_s)
    return runs
