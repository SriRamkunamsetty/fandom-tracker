"""Aspect-Based Sentiment Analysis (ABSA) Engine.
Extracts fine-grained aspect targets at the sentence level to avoid whole-comment cancellation."""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

from fandomwatch.stats import wilson

ASPECT_ONTOLOGY = {
    "acting": ["acting", "actor", "actors", "actress", "performance", "performances", "cast", "lead", "chemistry"],
    "story": ["story", "plot", "script", "writing", "screenplay", "ending", "twist", "storyline", "lore", "arc"],
    "visuals": ["visuals", "cinematography", "cgi", "effects", "vfx", "animation", "scenery", "shots", "lighting"],
    "music": ["music", "score", "soundtrack", "song", "theme", "audio", "composer"],
    "pacing": ["pacing", "slow", "rushed", "runtime", "drag", "length", "boring", "fast-paced"],
    "humor": ["humor", "jokes", "comedy", "laugh", "funny", "hilarious", "cringe"],
    "casting": ["casting", "recast", "replaced", "miscast", "cast", "role"],
    "price": ["price", "prices", "ticket", "tickets", "expensive", "overpriced", "cost", "subscription", "paywall", "greedy", "ripoff"],
    "marketing": ["trailer", "teaser", "spoiler", "spoilers", "marketing", "hype", "promo", "ad"],
}

ASPECT_MAP = {word: aspect for aspect, words in ASPECT_ONTOLOGY.items() for word in words}

POS_TERMS = {
    "love", "loved", "loving", "great", "amazing", "awesome", "incredible", "brilliant",
    "beautiful", "stunning", "perfect", "masterpiece", "fantastic", "excellent", "best",
    "good", "hyped", "excited", "epic", "fun", "hilarious", "funny", "gorgeous", "wow",
    "phenomenal", "superb", "impressive", "outstanding", "favorite", "favourite", "cool",
    "nice", "banger", "goosebumps", "worth", "fire", "slaps", "peak"
}

NEG_TERMS = {
    "hate", "hated", "terrible", "awful", "horrible", "bad", "worst", "boring", "cringe",
    "trash", "garbage", "disappointing", "disappointed", "overrated", "mess", "bland",
    "lazy", "ruined", "ruin", "flop", "waste", "dull", "weak", "predictable", "forgettable",
    "mid", "meh", "annoying", "pathetic", "greedy", "scam", "ripoff", "overpriced",
    "expensive", "boycott", "insulting", "sellout", "unwatchable", "disaster"
}

NEGATORS = {
    "not", "no", "never", "isn't", "wasn't", "don't", "doesn't", "didn't",
    "cannot", "can't", "won't", "hardly", "aren't", "wouldn't", "neither", "nor"
}

INTENSIFIERS = {
    "very": 1.5, "really": 1.5, "so": 1.4, "absolutely": 1.8, "super": 1.5,
    "extremely": 2.0, "incredibly": 1.8, "totally": 1.6, "completely": 1.7
}

EMOJI_POS = {"😍", "❤️", "❤", "🔥", "👏", "😂", "🤩", "👍", "🙌", "🎉"}
EMOJI_NEG = {"😡", "🤮", "👎", "😴", "😒", "💩", "🤢", "🤦"}

SPLIT_SENTENCE = re.compile(r"[.!?\n]+")
TOKEN_RE = re.compile(r"[a-z0-9']+|[\U0001F300-\U0001FAFF\u2600-\u27BF]")


@dataclass
class AspectResult:
    aspect: str
    mentions: int
    pos_count: int
    neg_count: int
    neu_count: int
    pos_share: float
    neg_share: float
    net_sentiment: float
    confidence_interval_95: List[float]


class AspectSentimentEngine:
    """Production Aspect-Based Sentiment Analysis parser."""

    def __init__(self, custom_ontology: Optional[Dict[str, List[str]]] = None):
        self.ontology = custom_ontology or ASPECT_ONTOLOGY
        self.aspect_map = {word: asp for asp, words in self.ontology.items() for word in words}

    def tokenize(self, text: str) -> List[str]:
        return TOKEN_RE.findall(text.lower().replace("’", "'"))

    def score_sentence(self, sentence: str) -> Tuple[float, str]:
        """Calculates polarity score & label ('pos', 'neg', 'neu') for an individual sentence."""
        tokens = self.tokenize(sentence)
        if not tokens:
            return 0.0, "neu"

        score = 0.0
        for i, token in enumerate(tokens):
            val = 0.0
            if token in POS_TERMS or token in EMOJI_POS:
                val = 1.0
            elif token in NEG_TERMS or token in EMOJI_NEG:
                val = -1.0

            if val == 0.0:
                continue

            # Lookback window for negation (up to 3 tokens prior)
            window = tokens[max(0, i - 3) : i]
            if any(w in NEGATORS or w.endswith("n't") for w in window):
                val = -val

            # Intensifier weighting
            for w in window:
                if w in INTENSIFIERS:
                    val *= INTENSIFIERS[w]

            score += val

        label = "pos" if score > 0.1 else "neg" if score < -0.1 else "neu"
        return score, label

    def analyze_comment(self, text: str) -> Dict[str, List[str]]:
        """Extracts {aspect: [sentence_labels]} for a comment."""
        aspect_labels = defaultdict(list)
        sentences = [s.strip() for s in SPLIT_SENTENCE.split(text) if s.strip()]

        for sent in sentences:
            tokens = self.tokenize(sent)
            detected_aspects = {self.aspect_map[w] for w in tokens if w in self.aspect_map}
            if detected_aspects:
                _, label = self.score_sentence(sent)
                for asp in detected_aspects:
                    aspect_labels[asp].append(label)

        return aspect_labels

    def aggregate_aspects(self, texts: Sequence[str]) -> List[AspectResult]:
        """Aggregates aspect-level metrics across a corpus of comments."""
        agg = defaultdict(Counter)

        for text in texts:
            sentences = [s.strip() for s in SPLIT_SENTENCE.split(text) if s.strip()]
            for sent in sentences:
                tokens = self.tokenize(sent)
                aspects = {self.aspect_map[w] for w in tokens if w in self.aspect_map}
                if aspects:
                    _, label = self.score_sentence(sent)
                    for asp in aspects:
                        agg[asp][label] += 1

        results = []
        for aspect, counts in agg.items():
            total = sum(counts.values())
            if total == 0:
                continue
            pos = counts["pos"]
            neg = counts["neg"]
            neu = counts["neu"]
            lo, hi = wilson(neg, total)
            res = AspectResult(
                aspect=aspect,
                mentions=total,
                pos_count=pos,
                neg_count=neg,
                neu_count=neu,
                pos_share=pos / total,
                neg_share=neg / total,
                net_sentiment=(pos - neg) / total,
                confidence_interval_95=[round(lo, 4), round(hi, 4)],
            )
            results.append(res)

        results.sort(key=lambda x: x.mentions, reverse=True)
        return results
