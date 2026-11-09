"""SYNTHETIC comments (is_sample=1). 'Steel Tide' gets a two-day price/recast backlash."""
import random
from datetime import datetime, timedelta, timezone

from .db import get_or_create_title, iso


TITLES = [("Iron Meridian", "action"), ("Steel Tide", "action"), ("Last Bastion", "action"), ("Zero Hour Protocol", "action"),
          ("The Quiet Orchard", "drama"), ("Salt and Ember", "drama"), ("Paper Lanterns", "drama"), ("A Winter Letter", "drama"),
          ("Pause Button", "comedy"), ("Roommate Wanted", "comedy"), ("Bad Influence", "comedy"), ("Plus One", "comedy")]


POS_S = ["Love the {a}.", "The {a} is absolutely amazing!", "Great {a}, can't wait to see it.", "Best {a} I've seen in years.", "Honestly the {a} looks stunning 🔥"]


NEG_S = ["The {a} looks terrible.", "Disappointed by the {a}.", "Boring {a}, not a fan.", "The {a} is a mess.", "Worst {a} ever, total flop."]


NEU_S = ["Watching this at midnight.", "When does this come out?", "Saw the {a} mentioned in the news."]


BACKLASH_S = ["Ticket prices are greedy, total ripoff.", "Recast the lead? Insulting, I will boycott.", "Overpriced tickets and a lazy recast, no thanks."]


ASPECT_WORDS = ["acting", "story", "visuals", "music", "pacing", "humor"]


def seed_comments(conn, seed_value=3, days=14, per_day=40):
    """SYNTHETIC comments (is_sample=1). 'Steel Tide' gets a two-day price/recast backlash."""
    rng = random.Random(seed_value)
    base = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    for ti, (name, genre) in enumerate(TITLES):
        tid = get_or_create_title(conn, name, genre)
        pos = rng.uniform(0.5, 0.75)
        for day in range(days):
            storm = ti == 1 and day in (8, 9)
            for k in range(per_day):
                a, r = rng.choice(ASPECT_WORDS), rng.random()
                if storm and r < 0.7:
                    text = rng.choice(BACKLASH_S)
                elif r < pos:
                    text = rng.choice(POS_S).format(a=a)
                elif r < pos + 0.18:
                    text = rng.choice(NEG_S).format(a=a)
                else:
                    text = rng.choice(NEU_S).format(a=a)
                ts = base + timedelta(days=ti + day, minutes=rng.randint(0, 1439))
                conn.execute("INSERT INTO comments (title_id, platform, native_id, posted_at, text, likes, is_sample) VALUES (?,?,?,?,?,?,1) "
                             "ON CONFLICT (platform, native_id) DO NOTHING",
                             (tid, "youtube", f"sample{ti}-{day}-{k}", iso(ts), text, rng.randint(0, 30)))
    conn.commit()


def seed_all(conn):
    seed_comments(conn)
