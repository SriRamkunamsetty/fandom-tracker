"""Dense semantic vector embeddings & retrieval for fan intelligence.
Implements a hybrid anchor-projection + subword hashing embedder for zero-dependency semantic operations."""
import hashlib
import math
import re
from typing import Dict, List, Sequence, Tuple

TOKEN_RE = re.compile(r"[a-z0-9']+|[\U0001F300-\U0001FAFF]")

# Semantic concept clusters mapped to anchor dimensions for semantic alignment
SEMANTIC_ANCHORS: Dict[str, List[str]] = {
    "audio": ["music", "score", "soundtrack", "song", "theme", "audio", "composer", "sound", "track"],
    "visual": ["visual", "visuals", "cinematography", "cgi", "effects", "vfx", "animation", "scenery", "shots", "look"],
    "performance": ["acting", "actor", "actors", "actress", "performance", "cast", "lead", "chemistry", "role"],
    "narrative": ["story", "plot", "script", "writing", "screenplay", "ending", "twist", "arc", "lore"],
    "commerce": ["price", "prices", "ticket", "tickets", "expensive", "cost", "scam", "ripoff", "greedy", "overpriced"],
    "comedy": ["humor", "jokes", "comedy", "laugh", "funny", "hilarious"],
    "positive": ["love", "great", "amazing", "awesome", "incredible", "brilliant", "perfect", "masterpiece", "fantastic", "fire"],
    "negative": ["hate", "terrible", "awful", "horrible", "bad", "worst", "boring", "trash", "garbage", "disaster"],
}


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower().replace("’", "'"))


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Computes cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class DenseEmbedder:
    """Dense semantic embedder combining semantic concept anchors with feature hashing."""

    def __init__(self, dim: int = 64):
        self.dim = dim
        self.num_anchors = len(SEMANTIC_ANCHORS)
        self.hash_dim = max(16, self.dim - self.num_anchors)

    def embed_text(self, text: str) -> List[float]:
        toks = tokenize(text)
        if not toks:
            return [0.0] * self.dim

        vec = [0.0] * self.dim

        # 1. Project onto Semantic Anchor Dimensions
        token_set = set(toks)
        for anchor_idx, (anchor_name, keywords) in enumerate(SEMANTIC_ANCHORS.items()):
            # Count keyword hits with frequency weight
            hit_count = sum(toks.count(kw) for kw in keywords if kw in token_set)
            if hit_count > 0:
                vec[anchor_idx] = math.log1p(hit_count) * 2.5

        # 2. Subword & N-gram Feature Hashing for the remaining dimensions
        for t in toks:
            # Word hash
            h_word = int(hashlib.md5(t.encode("utf-8")).hexdigest()[:8], 16)
            idx = self.num_anchors + (h_word % self.hash_dim)
            vec[idx] += 1.0

            # Character 3-grams for subword similarity (e.g. ticket ~ tickets)
            if len(t) >= 3:
                for j in range(len(t) - 2):
                    trigram = t[j : j + 3]
                    h_tri = int(hashlib.md5(trigram.encode("utf-8")).hexdigest()[:8], 16)
                    idx_tri = self.num_anchors + (h_tri % self.hash_dim)
                    vec[idx_tri] += 0.35

        # 3. L2 Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [x / norm for x in vec]
        return vec

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


def semantic_search(
    query: str,
    documents: Sequence[str],
    embeddings: Sequence[Sequence[float]] = None,
    embedder: DenseEmbedder = None,
    top_k: int = 5,
) -> List[Tuple[int, float, str]]:
    """Retrieves top-k documents matching query by semantic cosine similarity."""
    if not documents:
        return []

    embedder = embedder or DenseEmbedder()
    q_vec = embedder.embed_text(query)

    if embeddings is None:
        embeddings = embedder.embed_batch(documents)

    scores = []
    for i, (doc, doc_vec) in enumerate(zip(documents, embeddings)):
        sim = cosine_similarity(q_vec, doc_vec)
        scores.append((i, sim, doc))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]
