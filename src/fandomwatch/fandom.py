"""Project 3: Fandom health and share-of-voice. Comment-level sentiment, sentence-level aspect
sentiment, narrative clustering (TF-IDF), backlash detection, conversation share.

HONEST SCOPE: the default classifier is a small lexicon with negation handling. It is transparent and
dependency-free but far weaker than a trained model or an LLM; use `evaluate_classifier` on YOUR OWN
labelled comments before trusting any number, or plug in `LLMClassifier`."""
import csv
import json
import re
from collections import Counter, defaultdict
from math import log, sqrt

from .db import get_or_create_title, iso, now_iso, parse_ts
from .stats import robust_z, wilson

POS = set("love loved loving great amazing awesome incredible brilliant beautiful stunning perfect masterpiece fantastic excellent best good hyped excited epic fun hilarious funny gorgeous wow phenomenal superb impressive outstanding favorite favourite cool nice banger goosebumps worth".split())
NEG = set("hate hated terrible awful horrible bad worst boring cringe trash garbage disappointing disappointed overrated mess bland lazy ruined ruin flop waste dull weak predictable forgettable mid meh annoying pathetic greedy scam ripoff overpriced expensive boycott insulting sellout".split())
NEGATORS = {"not", "no", "never", "isn't", "wasn't", "don't", "doesn't", "didn't", "cannot", "can't", "won't", "hardly", "aren't", "wouldn't"}
INTENS = {"very", "really", "so", "absolutely", "super", "extremely", "incredibly"}
EMOJI_POS, EMOJI_NEG = set("😍❤🔥👏😂🤩👍"), set("😡🤮👎😴😒")
TOKEN = re.compile(r"[a-z']+|[\U0001F300-\U0001FAFF\u2764\u2600-\u27BF]")
ASPECTS = {
    "acting": "acting actor actors actress performance performances cast",
    "story": "story plot script writing screenplay ending twist storyline",
    "visuals": "visuals cinematography cgi effects vfx animation scenery shots",
    "music": "music score soundtrack song theme",
    "pacing": "pacing slow rushed runtime",
    "humor": "humor jokes comedy laugh",
    "casting": "casting recast replaced miscast",
    "price": "price prices ticket tickets expensive overpriced cost subscription paywall",
    "marketing": "trailer teaser spoiler spoilers marketing",
}
ASPECT_OF = {w: a for a, ws in ASPECTS.items() for w in ws.split()}
STOP = set("the and for that this with was are you its it's but have has had they them their there from what when who how just all can will would about out one more very really not get got".split())


def tokens(text):
    return TOKEN.findall(text.lower().replace("’", "'"))


def lexicon_score(text):
    toks, s = tokens(text), 0.0
    for i, t in enumerate(toks):
        v = 1.0 if (t in POS or t in EMOJI_POS) else -1.0 if (t in NEG or t in EMOJI_NEG) else 0.0
        if not v:
            continue
        window = toks[max(0, i - 3):i]
        if any(w in NEGATORS or w.endswith("n't") for w in window):
            v = -v
        if any(w in INTENS for w in window):
            v *= 1.5
        s += v
    return s


def lexicon_label(text):
    s = lexicon_score(text)
    return "pos" if s > 0 else "neg" if s < 0 else "neu"


class LLMClassifier:
    """Batch sentiment via any LLM callable. Returns 'unknown' when the reply cannot be parsed."""
    def __init__(self, llm, batch=20):
        self.llm, self.batch = llm, batch

    def classify_batch(self, texts):
        out = []
        for i in range(0, len(texts), self.batch):
            chunk = texts[i:i + self.batch]
            prompt = ("Classify the sentiment of each numbered social-media comment as pos, neg or neu. "
                      'Reply with a JSON array of exactly %d labels, nothing else.\n' % len(chunk)
                      + "\n".join(f"{n + 1}. {t[:300]!r}" for n, t in enumerate(chunk)))
            try:
                m = re.search(r"\[.*\]", self.llm(prompt, max_tokens=300), re.S)
                labels = [str(x).lower() for x in json.loads(m.group(0))]
                ok = len(labels) == len(chunk) and all(x in ("pos", "neg", "neu") for x in labels)
            except Exception:
                ok = False
            out += labels if ok else ["unknown"] * len(chunk)
        return out


def evaluate_classifier(pairs, classify=lexicon_label):
    """pairs: [(text, true_label)]. Returns accuracy, macro-F1, per-class P/R/F1 and a confusion matrix."""
    labs = ("pos", "neu", "neg")
    conf = {a: {b: 0 for b in labs} for a in labs}
    for text, truth in pairs:
        pred = classify(text)
        if truth in conf and pred in conf[truth]:
            conf[truth][pred] += 1
    per, n = {}, sum(sum(r.values()) for r in conf.values())
    for c in labs:
        tp = conf[c][c]; fp = sum(conf[o][c] for o in labs if o != c); fn = sum(conf[c][o] for o in labs if o != c)
        p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
        per[c] = {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0, "support": tp + fn}
    return {"n": n, "accuracy": sum(conf[c][c] for c in labs) / n if n else 0.0,
            "macro_f1": sum(v["f1"] for v in per.values()) / 3, "per_class": per, "confusion": conf}


def import_comments_csv(conn, path):
    """Columns: title, comment_id, posted_at, text [, platform, likes]. Bad rows rejected with reasons."""
    ok, rejected = 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        miss = [c for c in ("title", "comment_id", "posted_at", "text") if c not in (rd.fieldnames or [])]
        if miss:
            raise ValueError(f"CSV is missing required columns: {miss}")
        for n, row in enumerate(rd, start=2):
            try:
                if not row["text"].strip():
                    raise ValueError("empty text")
                tid = get_or_create_title(conn, row["title"].strip())
                conn.execute("INSERT INTO comments (title_id, platform, native_id, posted_at, text, likes) VALUES (?,?,?,?,?,?) "
                             "ON CONFLICT (platform, native_id) DO NOTHING",
                             (tid, (row.get("platform") or "csv").strip().lower(), row["comment_id"].strip(),
                              iso(parse_ts(row["posted_at"])), row["text"].strip(), int(float(row.get("likes") or 0))))
                ok += 1
            except (ValueError, KeyError) as exc:
                rejected.append({"line": n, "reason": str(exc)})
    conn.commit()
    return {"accepted": ok, "rejected": rejected}


def _load(conn, title_id):
    return [(r["posted_at"], r["text"], int(r["likes"])) for r in
            conn.execute("SELECT posted_at, text, likes FROM comments WHERE title_id=? ORDER BY posted_at", (title_id,))]


def aspect_sentiment(texts):
    """Sentence-level: each sentence is attributed to the aspects it mentions and scored on its own."""
    agg = defaultdict(lambda: Counter())
    for t in texts:
        for sent in re.split(r"[.!?\n]+", t):
            asp = {ASPECT_OF[w] for w in tokens(sent) if w in ASPECT_OF}
            if asp:
                lab = lexicon_label(sent)
                for a in asp:
                    agg[a][lab] += 1
    out = []
    for a, c in agg.items():
        n = sum(c.values())
        out.append({"aspect": a, "n": n, "pos": c["pos"] / n, "neg": c["neg"] / n, "net": (c["pos"] - c["neg"]) / n})
    return sorted(out, key=lambda x: -x["n"])


def _cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def cluster_narratives(texts, threshold=0.25, min_size=3, max_n=2000, top=5):
    """Greedy single-pass TF-IDF clustering. Output: the recurring themes, not a topic-model claim."""
    texts = texts[:max_n]
    toks = [[t for t in tokens(x) if len(t) > 2 and t not in STOP and t[0].isalpha()] for x in texts]
    df = Counter(w for t in toks for w in set(t))
    N = len(toks)
    idf = {w: log((1 + N) / (1 + d)) + 1 for w, d in df.items()}

    def vec(ts):
        v = {w: (1 + log(n)) * idf[w] for w, n in Counter(ts).items()}
        nm = sqrt(sum(x * x for x in v.values()))
        return {w: x / nm for w, x in v.items()} if nm else {}

    vecs, clusters = [vec(t) for t in toks], []
    for i, v in enumerate(vecs):
        if not v:
            continue
        best, bs = None, 0.0
        for c in clusters:
            s = _cos(v, c["cent"])
            if s > bs:
                best, bs = c, s
        if best is not None and bs >= threshold:
            best["members"].append(i)
            for w, x in v.items():
                best["sum"][w] += x
            nm = sqrt(sum(x * x for x in best["sum"].values()))
            best["cent"] = {w: x / nm for w, x in best["sum"].items()}
        else:
            clusters.append({"members": [i], "sum": Counter(v), "cent": dict(v)})
    out = []
    for c in sorted(clusters, key=lambda c: -len(c["members"])):
        if len(c["members"]) < min_size:
            continue
        ex = max(c["members"], key=lambda i: _cos(vecs[i], c["cent"]))
        labs = Counter(lexicon_label(texts[i]) for i in c["members"])
        n = len(c["members"])
        out.append({"size": n, "share": n / N, "terms": [w for w, _ in c["sum"].most_common(4)],
                    "net_sentiment": (labs["pos"] - labs["neg"]) / n, "example": texts[ex][:160]})
        if len(out) == top:
            break
    return out


def detect_backlash(rows, min_day_n=20, min_neg=10, z_thresh=3.5, min_neg_share=0.35):
    """Days where the NEGATIVE SHARE is a robust-z outlier, with enough volume to mean something.
    Consecutive days merge into one episode. Returns [] when there are too few usable days."""
    days = defaultdict(lambda: [0, 0])
    for ts, text, _ in rows:
        d = days[ts[:10]]
        d[0] += 1
        d[1] += lexicon_label(text) == "neg"
    usable = sorted((d, v) for d, v in days.items() if v[0] >= min_day_n)
    if len(usable) < 6:
        return []
    shares = [v[1] / v[0] for _, v in usable]
    zs = robust_z(shares)
    flagged = [i for i, (z, (_, v)) in enumerate(zip(zs, usable)) if z >= z_thresh and shares[i] >= min_neg_share and v[1] >= min_neg]
    eps, cur = [], []
    for i in flagged:
        if cur and i != cur[-1] + 1:
            eps.append(cur); cur = []
        cur.append(i)
    if cur:
        eps.append(cur)
    out = []
    for ep in eps:
        peak = max(ep, key=lambda i: shares[i])
        neg_n = sum(usable[i][1][1] for i in ep)
        sev = "critical" if shares[peak] >= 0.6 and neg_n >= 50 else "high" if shares[peak] >= 0.5 else "watch"
        dset = {usable[i][0] for i in ep}
        negs = [t for ts, t, _ in rows if ts[:10] in dset and lexicon_label(t) == "neg"]
        out.append({"start": usable[ep[0]][0], "end": usable[ep[-1]][0], "peak_day": usable[peak][0],
                    "peak_neg_share": shares[peak], "neg_comments": neg_n, "severity": sev,
                    "top_aspects": [a["aspect"] for a in aspect_sentiment(negs)[:3]],
                    "themes": [c["terms"] for c in cluster_narratives(negs, min_size=3, top=2)]})
    return out


def daily_series(rows):
    """[{date, n, neg_share}] per UTC day, for the sentiment timeline."""
    days = defaultdict(lambda: [0, 0])
    for ts, text, _ in rows:
        d = days[ts[:10]]
        d[0] += 1
        d[1] += lexicon_label(text) == "neg"
    return [{"date": d, "n": v[0], "neg_share": v[1] / v[0]} for d, v in sorted(days.items())]


def conversation_share(conn, title_ids):
    """Share of tracked comment volume (a mention-based share of voice) and net sentiment per title."""
    out, total = {}, 0
    for t in title_ids:
        rows = _load(conn, t)
        labs = Counter(lexicon_label(x[1]) for x in rows)
        out[t] = {"comments": len(rows), "net_sentiment": (labs["pos"] - labs["neg"]) / len(rows) if rows else None}
        total += len(rows)
    for t in out:
        out[t]["share"] = out[t]["comments"] / total if total else None
    return out


def fandom_report(conn, title_id, peer_ids=()):
    rows = _load(conn, title_id)
    n = len(rows)
    if n == 0:
        return {"n": 0, "note": "no comments ingested for this title"}
    texts = [r[1] for r in rows]
    labs = Counter(lexicon_label(t) for t in texts)
    lo, hi = wilson(labs["neg"], n)
    share = conversation_share(conn, [title_id, *peer_ids])[title_id]
    return {"n": n, "sentiment": {k: labs[k] / n for k in ("pos", "neu", "neg")},
            "neg_share_ci95": [lo, hi], "net_sentiment": (labs["pos"] - labs["neg"]) / n,
            "aspects": aspect_sentiment(texts), "narratives": cluster_narratives(texts),
            "backlash": detect_backlash(rows), "daily": daily_series(rows), "conversation_share": share["share"],
            "classifier": "lexicon (unvalidated until you run `fandomwatch fandom-eval` on your own labels)"}
