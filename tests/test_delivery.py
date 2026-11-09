import csv
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from fandomwatch.cli import main
from fandomwatch.db import connect, get_or_create_title
from fandomwatch.fandom import (LLMClassifier, aspect_sentiment, cluster_narratives, conversation_share, daily_series, detect_backlash,
                          evaluate_classifier, fandom_report, import_comments_csv, lexicon_label)
from fandomwatch.ingest import QuotaExceeded, YouTubeClient, ingest_youtube_comments
from fandomwatch.sample_data import seed_all, seed_comments
from fandomwatch.stats import pct_rank, robust_z, wilson
from fandomwatch.web import App, make_handler



class DailySeries(unittest.TestCase):
    def test_daily_series_counts_and_shares(self):
        rows = [("2026-01-01T10:00:00Z", "love it", 0), ("2026-01-01T11:00:00Z", "awful flop", 0), ("2026-01-02T09:00:00Z", "terrible", 0)]
        self.assertEqual(daily_series(rows), [{"date": "2026-01-01", "n": 2, "neg_share": 0.5}, {"date": "2026-01-02", "n": 1, "neg_share": 1.0}])

    def test_report_includes_daily_and_backlash_band_dates_exist_in_it(self):
        c = connect(); seed_comments(c)
        r = fandom_report(c, 2, [1, 3])
        dates = {d["date"] for d in r["daily"]}
        self.assertTrue(r["backlash"]); self.assertTrue(all(b["start"] in dates and b["end"] in dates for b in r["backlash"]))


class Collection(unittest.TestCase):
    def test_comments_over_real_sockets_with_pagination_retry_and_disabled(self):
        state, log = {"n": 0}, []
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                log.append(self.path); state["n"] += 1
                q = parse_qs(urlsplit(self.path).query)
                if q["videoId"][0] == "off":
                    code, out = 403, json.dumps({"error": {"errors": [{"reason": "commentsDisabled"}]}})
                elif state["n"] == 1:
                    code, out = 503, "busy"
                else:
                    page2 = "pageToken" in q
                    code = 200
                    out = json.dumps({"items": [{"id": "c2" if page2 else "c1", "snippet": {"topLevelComment": {"snippet": {"textOriginal": "hi", "publishedAt": "2026-01-02T00:00:00Z", "likeCount": 1}}}}],
                                      **({} if page2 else {"nextPageToken": "T2"})})
                self.send_response(code); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out.encode())
            def log_message(self, *a): pass
        srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            cl = YouTubeClient("MYKEY", sleep=lambda s: None); cl.BASE = f"http://127.0.0.1:{srv.server_address[1]}/youtube/v3/"
            c = connect()
            self.assertEqual(ingest_youtube_comments(c, cl, "T", "v", max_pages=3), 2)       # 503 retried, then followed nextPageToken
            self.assertEqual(ingest_youtube_comments(c, cl, "T", "v", max_pages=3), 2)
            self.assertEqual(c.execute("SELECT COUNT(*) n FROM comments").fetchone()["n"], 2)  # idempotent
            self.assertEqual(cl.comments("off"), [])
        finally:
            srv.shutdown(); srv.server_close()

    def test_collect_isolates_bad_titles_and_quota_stops(self):
        from fandomwatch.collect import collect_once, schedule
        page = json.dumps({"items": [{"id": "c1", "snippet": {"topLevelComment": {"snippet": {"textOriginal": "hi", "publishedAt": "2026-01-02T00:00:00Z", "likeCount": 0}}}}]})
        cfg = {"titles": [{"name": "Bad", "videos": {"trailer": ["x"]}}, {"name": "Good", "videos": {"trailer": ["v"]}}]}
        cl = YouTubeClient("k", fetch=lambda u: (403, "no") if "videoId=x" in u else (200, page), sleep=lambda s: None)
        s = collect_once(connect(), cl, cfg)
        self.assertEqual((s["titles"], len(s["errors"])), (1, 1))
        capped = YouTubeClient("k", fetch=lambda u: (200, page), daily_quota=1)
        self.assertEqual(schedule(connect(), capped, cfg, 1, max_runs=5, sleep=lambda s: None, log=lambda *a: None), 0)


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = connect(check_same_thread=False); seed_all(conn)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(conn)))
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def call(self, p, data=None):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + p, data=data)) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_api_page_and_hardening(self):
        s, h, b = self.call("/")
        self.assertEqual(s, 200); self.assertNotIn(b"innerHTML", b); self.assertIn("default-src 'none'", h["Content-Security-Policy"])
        titles = json.loads(self.call("/api/titles")[2]); self.assertEqual(len(titles), 12)
        r = json.loads(self.call("/api/fandom/2")[2]); self.assertTrue(r["backlash"] and r["daily"])
        for p in ("/api/fandom/9999", "/api/fandom/abc", "/etc/passwd"):
            self.assertEqual(self.call(p)[0], 404)
        self.assertEqual(self.call("/api/titles", data=b"{}")[0], 405)


class Cli(unittest.TestCase):
    def test_fandom_eval_runs_and_saves_on_a_labelled_csv(self):
        d = tempfile.mkdtemp(); path = os.path.join(d, "l.csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["text", "label"]); w.writerows([("love it", "pos"), ("awful", "neg"), ("when does it come out", "neu"), ("great film", "pos")])
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["fandom-eval", path, "--save", "--validation-dir", os.path.join(d, "v")])
        out = json.loads(buf.getvalue()); self.assertEqual(out["lexicon"]["n"], 4); self.assertEqual(out["lexicon"]["accuracy"], 1.0)
        with open(os.path.join(d, "v", "fandom_eval.json")) as fh:
            self.assertEqual(json.load(fh)["lexicon"]["n"], 4)

    def test_report_command(self):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["report", "--demo", "--title", "Steel Tide", "--format", "json"])
        self.assertTrue(json.loads(buf.getvalue())["backlash"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["report", "--demo", "--title", "Iron Meridian"])
        self.assertIn("BACKLASH WATCH", buf.getvalue()); self.assertIn("none detected", buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["report", "--demo", "--title", "Steel Tide"])
        self.assertIn("[HIGH]", buf.getvalue()); self.assertIn("price", buf.getvalue())


class Browser(unittest.TestCase):
    def test_timeline_and_backlash_render_in_a_real_browser(self):
        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start(); browser = pw.chromium.launch()
        except Exception:
            self.skipTest("Playwright/Chromium not available")
        conn = connect(check_same_thread=False); seed_all(conn)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(conn))); threading.Thread(target=srv.serve_forever, daemon=True).start()
        errors = []
        try:
            page = browser.new_page(); page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{srv.server_address[1]}/"); page.wait_for_selector("#slate button")
            for i in (0, 1, 7):
                page.locator("#slate button").nth(i).click(); page.wait_for_timeout(500)
                body = page.inner_text("main")
                for bad in ("[object", "undefined", "NaN"):
                    self.assertNotIn(bad, body)
            page.locator("#slate button").nth(1).click(); page.wait_for_timeout(500)
            self.assertIn("BACKLASH WATCH", page.inner_text("main").upper()); self.assertTrue(page.locator("main svg rect").count() > 10)
        finally:
            browser.close(); pw.stop(); srv.shutdown(); srv.server_close()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
