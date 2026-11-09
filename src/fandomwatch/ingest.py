"""YouTube comment collection (public top-level comments: text, time, likes only; no author data)."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .db import get_or_create_title, iso, now_iso, parse_ts


def _log_run(conn, source, started, status, ok, rejected, quota=0):
    conn.execute(
        "INSERT INTO ingest_runs (source, started_at, status, rows_ok, rows_rejected, quota_units) "
        "VALUES (?,?,?,?,?,?)", (source, started, status, ok, rejected, quota))


class QuotaExceeded(RuntimeError):
    pass


class YouTubeError(RuntimeError):
    def __init__(self, status, body):
        super().__init__(f"YouTube API error {status}: {body[:200]}")
        self.status, self.body = status, body


def _default_fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


class YouTubeClient:
    """Each list call costs 1 quota unit (videos: up to 50 ids; commentThreads: up to 100 comments)."""
    BASE = "https://www.googleapis.com/youtube/v3/"

    def __init__(self, api_key=None, fetch=None, daily_quota=10_000, max_retries=4, sleep=time.sleep):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self.fetch, self.sleep = fetch or _default_fetch, sleep
        self.daily_quota, self.max_retries, self.used = daily_quota, max_retries, 0

    def _call(self, endpoint, params):
        if self.used + 1 > self.daily_quota:
            raise QuotaExceeded(f"{self.used}/{self.daily_quota} units used")
        url = self.BASE + endpoint + "?" + urllib.parse.urlencode({**params, "key": self.api_key})
        for attempt in range(self.max_retries + 1):
            status, body = self.fetch(url)
            if status == 200:
                self.used += 1
                return json.loads(body)
            if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                self.sleep(2 ** attempt)
                continue
            raise YouTubeError(status, body)

    def video_stats(self, video_ids):
        out = []
        for i in range(0, len(video_ids), 50):
            data = self._call("videos", {"part": "snippet,statistics", "id": ",".join(video_ids[i:i + 50])})
            for item in data.get("items", []):
                st = item.get("statistics", {})
                out.append({"id": item["id"], "published_at": item["snippet"]["publishedAt"],
                            "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                            "comments": int(st.get("commentCount", 0))})
        return out

    def comments(self, video_id, max_pages=2):
        """Top-level comments, newest first. Returns [] if the video has comments disabled."""
        out, token = [], None
        for _ in range(max_pages):
            params = {"part": "snippet", "videoId": video_id, "maxResults": 100, "order": "time", "textFormat": "plainText"}
            if token:
                params["pageToken"] = token
            try:
                data = self._call("commentThreads", params)
            except YouTubeError as exc:
                if "commentsDisabled" in exc.body:
                    return out
                raise
            for it in data.get("items", []):
                sn = it["snippet"]["topLevelComment"]["snippet"]
                out.append({"id": it["id"], "text": sn.get("textOriginal") or sn.get("textDisplay", ""),
                            "posted_at": sn["publishedAt"], "likes": int(sn.get("likeCount", 0))})
            token = data.get("nextPageToken")
            if not token:
                break
        return out


def ingest_youtube_comments(conn, client, title_name, video_id, max_pages=2):
    """Store top-level public comments (text + timestamp + likes only; no author data)."""
    started = now_iso()
    tid = get_or_create_title(conn, title_name)
    rows = client.comments(video_id, max_pages)
    for r in rows:
        conn.execute("INSERT INTO comments (title_id, platform, native_id, posted_at, text, likes) VALUES (?,?,?,?,?,?) "
                     "ON CONFLICT (platform, native_id) DO NOTHING",
                     (tid, "youtube", r["id"], iso(parse_ts(r["posted_at"])), r["text"], r["likes"]))
    _log_run(conn, "youtube-comments", started, "ok", len(rows), 0, client.used)
    conn.commit()
    return len(rows)
