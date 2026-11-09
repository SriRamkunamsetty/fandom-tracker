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


def tmp_csv(header, rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    w = csv.DictWriter(f, fieldnames=header); w.writeheader(); w.writerows(rows); f.close()
    return f.name


class Stats(unittest.TestCase):
    def test_wilson_and_percentile(self):
        lo, hi = wilson(8, 10); self.assertAlmostEqual(lo, 0.490, places=2); self.assertAlmostEqual(hi, 0.943, places=2)
        self.assertEqual(wilson(0, 0), (0.0, 1.0))
        self.assertEqual(pct_rank([1, 2, 3, 4], 4), 87.5)
        self.assertGreater(robust_z([1, 1, 1, 1, 9])[-1], 3.5)


class Fandom(unittest.TestCase):
    def test_lexicon_negation_and_emoji(self):
        self.assertEqual(lexicon_label("This is not good"), "neg")
        self.assertEqual(lexicon_label("not bad at all"), "pos")
        self.assertEqual(lexicon_label("absolutely love it 🔥"), "pos")
        self.assertEqual(lexicon_label("when does it release"), "neu")

    def test_evaluate_classifier_math(self):
        pairs = [("love", "pos"), ("great", "pos"), ("awful", "neg"), ("love", "neg"), ("meh?", "neu")]
        r = evaluate_classifier(pairs)
        self.assertEqual(r["n"], 5); self.assertAlmostEqual(r["accuracy"], 3 / 5)     # love(neg) wrong, 'meh?' -> neu? meh is NEG word
        self.assertEqual(r["confusion"]["pos"]["pos"], 2)

    def test_aspects_are_sentence_level(self):
        a = {x["aspect"]: x for x in aspect_sentiment(["The acting is brilliant. The story is a mess."])}
        self.assertEqual(a["acting"]["net"], 1.0); self.assertEqual(a["story"]["net"], -1.0)

    def test_clusters_separate_themes(self):
        texts = ["ticket prices are far too expensive"] * 4 + ["love the soundtrack and music score"] * 4 + ["random unrelated words here"]
        terms = [set(c["terms"]) for c in cluster_narratives(texts, min_size=3)]
        self.assertEqual(len(terms), 2)
        self.assertTrue(any({"ticket", "prices"} & t for t in terms) and any({"soundtrack", "music"} & t for t in terms))

    def test_backlash_on_explicit_rows_and_no_false_alarm(self):
        def day(d, n, neg):
            return [(f"2026-01-{d:02d}T10:00:00Z", "terrible awful flop" if i < neg else "love it", 0) for i in range(n)]
        calm = [r for d in range(1, 11) for r in day(d, 30, 4 + d % 3)]
        self.assertEqual(detect_backlash(calm), [])
        storm = calm + day(11, 30, 24) + day(12, 30, 26)
        eps = detect_backlash(storm)
        self.assertEqual(len(eps), 1); self.assertEqual(eps[0]["start"], "2026-01-11"); self.assertEqual(eps[0]["end"], "2026-01-12")
        self.assertIn(eps[0]["severity"], ("high", "critical"))
        self.assertEqual(detect_backlash(day(1, 5, 5)), [])                              # too little data -> nothing, not a guess

    def test_demo_backlash_found_on_the_right_title_only(self):
        c = connect(); seed_comments(c)
        self.assertTrue(fandom_report(c, 2, [1, 3])["backlash"])
        self.assertEqual(fandom_report(c, 1, [2, 3])["backlash"], [])
        self.assertAlmostEqual(sum(v["share"] for v in conversation_share(c, list(range(1, 13))).values()), 1.0)

    def test_csv_import_and_empty_title(self):
        c = connect()
        p = tmp_csv(["title", "comment_id", "posted_at", "text"], [
            dict(title="X", comment_id="1", posted_at="2026-01-01T00:00:00Z", text="great"),
            dict(title="X", comment_id="2", posted_at="not a date", text="bad date"),
            dict(title="X", comment_id="3", posted_at="2026-01-01T00:00:00Z", text="  ")])
        res = import_comments_csv(c, p); os.unlink(p)
        self.assertEqual((res["accepted"], len(res["rejected"])), (1, 2))
        self.assertEqual(fandom_report(c, get_or_create_title(c, "Empty"))["n"], 0)

    def test_llm_classifier_parse_and_unknown(self):
        self.assertEqual(LLMClassifier(lambda p, **k: '["pos","neg"]').classify_batch(["a", "b"]), ["pos", "neg"])
        self.assertEqual(LLMClassifier(lambda p, **k: "sorry").classify_batch(["a", "b"]), ["unknown", "unknown"])
        self.assertEqual(LLMClassifier(lambda p, **k: '["pos"]').classify_batch(["a", "b"]), ["unknown", "unknown"])   # wrong length


if __name__ == "__main__":
    unittest.main()
