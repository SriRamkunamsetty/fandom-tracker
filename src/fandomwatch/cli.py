"""FandomWatch command line. Run `fandomwatch <command> -h` for options."""
import argparse
import csv
import json
import os

from . import __version__
from .db import connect
from .fandom import LLMClassifier, evaluate_classifier, fandom_report, import_comments_csv
from .ingest import QuotaExceeded, YouTubeClient, ingest_youtube_comments


def open_db(a):
    if getattr(a, "demo", False):
        from .sample_data import seed_all
        conn = connect(check_same_thread=False)
        seed_all(conn)
        return conn
    return connect(a.db, check_same_thread=False)


def _title_id(conn, name):
    row = conn.execute("SELECT id FROM titles WHERE name=?", (name,)).fetchone()
    if not row:
        raise SystemExit(f"unknown title: {name}")
    return row["id"]


def _text(name, r):
    if not r["n"]:
        return f"{name}: no comments ingested"
    s, (lo, hi) = r["sentiment"], r["neg_share_ci95"]
    cs = "n/a" if r["conversation_share"] is None else f"{r['conversation_share']:.1%}"
    out = [f"{name}: {r['n']} comments", f"  sentiment       {s['pos']:.0%} positive / {s['neu']:.0%} neutral / {s['neg']:.0%} negative   (negative share 95% CI {lo:.1%} to {hi:.1%})",
           f"  net sentiment   {r['net_sentiment'] * 100:+.0f} points      conversation share {cs}", f"  classifier      {r['classifier']}", "", "BACKLASH WATCH"]
    if not r["backlash"]:
        out.append("  none detected")
    for b in r["backlash"]:
        out.append(f"  [{b['severity'].upper()}] {b['start']} to {b['end']}: peak {b['peak_neg_share']:.0%} negative, {b['neg_comments']} negative comments")
        out.append(f"         aspects: {', '.join(b['top_aspects']) or 'n/a'}")
        if b["themes"]:
            out.append("         recurring terms: " + "; ".join(" / ".join(t) for t in b["themes"]))
    out += ["", "ASPECTS (sentence-level)"] + [f"  {a['aspect']:<10}{a['n']:>5} mentions   net {a['net']:+.2f}" for a in r["aspects"]]
    out += ["", "RECURRING NARRATIVES"] + [f"  {n['share']:>5.1%}  {' / '.join(n['terms']):<34} \"{n['example'][:48]}\"" for n in r["narratives"]]
    return "\n".join(out)


def build_parser():
    p = argparse.ArgumentParser(prog="fandomwatch", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=os.environ.get("DATABASE_URL", "fandomwatch.db"), help="SQLite path or postgresql:// DSN")
    common.add_argument("--demo", action="store_true", help="use in-memory SYNTHETIC demo data")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("report", parents=[common], help="full fandom report for a title"); d.add_argument("--title", default="Steel Tide"); d.add_argument("--format", choices=["text", "json"], default="text")
    w = sub.add_parser("serve", parents=[common], help="read-only dashboard"); w.add_argument("--host", default="127.0.0.1"); w.add_argument("--port", type=int, default=8000)
    sub.add_parser("import-comments", parents=[common], help="title,comment_id,posted_at,text[,platform,likes]").add_argument("path")
    y = sub.add_parser("ingest-youtube", parents=[common], help="top-level comments of one video"); y.add_argument("--title", required=True); y.add_argument("--video", required=True); y.add_argument("--pages", type=int, default=2)
    c = sub.add_parser("collect", parents=[common], help="one pass from a titles.json config"); c.add_argument("--config", required=True)
    s = sub.add_parser("schedule", parents=[common]); s.add_argument("--config", required=True); s.add_argument("--every-hours", type=float, default=6); s.add_argument("--max-runs", type=int)
    e = sub.add_parser("fandom-eval", help="accuracy / macro-F1 on YOUR labelled CSV (text,label in pos|neu|neg)")
    e.add_argument("path"); e.add_argument("--llm", choices=["anthropic", "gemini"], help="also score an LLM classifier"); e.add_argument("--save", action="store_true"); e.add_argument("--validation-dir", default="validation")
    sub.add_parser("check-youtube", help="live smoke test of YOUTUBE_API_KEY")
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        _dispatch(a)
    except (RuntimeError, ValueError, OSError) as exc:
        raise SystemExit(f"error: {exc}")


def _dispatch(a):
    if a.cmd == "report":
        a.demo = a.demo or False
        conn = open_db(a); tid = _title_id(conn, a.title)
        rep = fandom_report(conn, tid, [r["id"] for r in conn.execute("SELECT id FROM titles WHERE id<>?", (tid,))])
        print(json.dumps(rep, indent=2, default=str) if a.format == "json" else _text(a.title, rep))
    elif a.cmd == "serve":
        from .web import serve
        serve(open_db(a), a.host, a.port)
    elif a.cmd == "import-comments":
        r = import_comments_csv(open_db(a), a.path); print(f"accepted={r['accepted']} rejected={len(r['rejected'])}")
        for x in r["rejected"][:20]:
            print(f"  line {x['line']}: {x['reason']}")
    elif a.cmd == "ingest-youtube":
        client = YouTubeClient()
        try:
            print(f"stored {ingest_youtube_comments(open_db(a), client, a.title, a.video, a.pages)} comments, quota used {client.used}")
        except QuotaExceeded as exc:
            raise SystemExit(f"quota exhausted: {exc}")
    elif a.cmd in ("collect", "schedule"):
        from .collect import collect_once, load_config, schedule
        conn, cfg, client = open_db(a), load_config(a.config), YouTubeClient()
        if a.cmd == "collect":
            print(json.dumps(collect_once(conn, client, cfg), indent=2))
        else:
            schedule(conn, client, cfg, a.every_hours * 3600, max_runs=a.max_runs)
    elif a.cmd == "fandom-eval":
        with open(a.path, newline="", encoding="utf-8-sig") as fh:
            pairs = [(r["text"], r["label"].strip().lower()) for r in csv.DictReader(fh)]
        from .fandom import lexicon_label
        out = {"lexicon": evaluate_classifier(pairs, lexicon_label)}
        if a.llm:
            from .llm import get_llm
            labs = dict(zip([t for t, _ in pairs], LLMClassifier(get_llm(a.llm)).classify_batch([t for t, _ in pairs])))
            out["llm"] = evaluate_classifier(pairs, lambda t: labs[t])
        print(json.dumps(out, indent=2))
        if a.save:
            os.makedirs(a.validation_dir, exist_ok=True)
            with open(os.path.join(a.validation_dir, "fandom_eval.json"), "w", encoding="utf-8") as fh:
                json.dump({k: {"n": v["n"], "accuracy": v["accuracy"], "macro_f1": v["macro_f1"]} for k, v in out.items()} | {"source": os.path.basename(a.path)}, fh, indent=2)
    elif a.cmd == "check-youtube":
        client = YouTubeClient()
        if not client.api_key:
            raise SystemExit("YOUTUBE_API_KEY is not set")
        stats = client.video_stats(["dQw4w9WgXcQ"])
        print(f"OK: key works, got {len(stats)} video, quota used {client.used}" if stats else "Key accepted but no video returned")


if __name__ == "__main__":
    main()
