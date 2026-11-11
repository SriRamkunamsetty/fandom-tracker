"""Semantic Narrative Clustering Engine.
Groups recurring narrative themes across thousands of comments using hybrid dense & TF-IDF vector representations."""
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .embeddings import DenseEmbedder, cosine_similarity

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "was", "are", "you", "its", "it's",
    "but", "have", "has", "had", "they", "them", "their", "there", "from", "what",
    "when", "who", "how", "just", "all", "can", "will", "would", "about", "out",
    "one", "more", "very", "really", "not", "get", "got", "like", "movie", "film",
    "trailer", "video", "see", "seen", "watch", "watched", "watching", "even", "much"
}

TOKEN_RE = re.compile(r"[a-z']+")


@dataclass
class NarrativeCluster:
    cluster_id: int
    size: int
    share: float
    keywords: List[str]
    representative_text: str
    net_sentiment: float
    thematic_title: str


class SemanticClusterer:
    """Clustering engine for discovering recurring narrative threads."""

    def __init__(self, similarity_threshold: float = 0.20, min_cluster_size: int = 2):
        self.threshold = similarity_threshold
        self.min_size = min_cluster_size
        self.embedder = DenseEmbedder(dim=64)

    def _tokenize(self, text: str) -> List[str]:
        return [w for w in TOKEN_RE.findall(text.lower()) if len(w) > 2 and w not in STOPWORDS]

    def cluster(
        self,
        texts: Sequence[str],
        sentiment_scores: Optional[Sequence[float]] = None,
        top_clusters: int = 6,
        max_samples: int = 2500,
    ) -> List[NarrativeCluster]:
        """Runs single-pass centroid clustering over texts."""
        if not texts:
            return []

        sample_texts = texts[:max_samples]
        n_samples = len(sample_texts)

        # 1. Compute TF-IDF vocabulary weights
        tokenized_corpus = [self._tokenize(t) for t in sample_texts]
        df = Counter(w for doc in tokenized_corpus for w in set(doc))
        idf = {w: math.log((1 + n_samples) / (1 + count)) + 1.0 for w, count in df.items()}

        # 2. Build normalized sparse vectors
        doc_vectors = []
        for doc in tokenized_corpus:
            tf = Counter(doc)
            v = {w: (1.0 + math.log(cnt)) * idf[w] for w, cnt in tf.items()}
            norm = math.sqrt(sum(x * x for x in v.values()))
            doc_vectors.append({w: x / norm for w, x in v.items()} if norm > 0 else {})

        # Dense fallback embeddings
        dense_vecs = self.embedder.embed_batch(sample_texts)

        # 3. Greedy single-pass clustering
        clusters: List[Dict] = []
        for i, (v, d_vec) in enumerate(zip(doc_vectors, dense_vecs)):
            best_idx, best_sim = -1, 0.0
            for c_idx, cluster in enumerate(clusters):
                # Sparse cosine similarity
                cent = cluster["centroid"]
                sparse_sim = sum(val * cent.get(w, 0.0) for w, val in v.items())
                # Dense similarity
                dense_sim = cosine_similarity(d_vec, cluster["dense_centroid"])
                # Hybrid similarity
                sim = max(sparse_sim, dense_sim * 0.8)
                if sim > best_sim:
                    best_idx, best_sim = c_idx, sim

            if best_idx >= 0 and best_sim >= self.threshold:
                c = clusters[best_idx]
                c["members"].append(i)
                for w, val in v.items():
                    c["term_sum"][w] = c["term_sum"].get(w, 0.0) + val
                norm = math.sqrt(sum(x * x for x in c["term_sum"].values()))
                c["centroid"] = {w: x / norm for w, x in c["term_sum"].items()} if norm > 0 else {}
                # Update dense centroid
                m_count = len(c["members"])
                c["dense_centroid"] = [
                    (old * (m_count - 1) + new) / m_count
                    for old, new in zip(c["dense_centroid"], d_vec)
                ]
            else:
                clusters.append({
                    "members": [i],
                    "term_sum": dict(v),
                    "centroid": dict(v),
                    "dense_centroid": list(d_vec),
                })

        # 4. Filter, sort, and package narrative clusters
        valid_clusters = [c for c in clusters if len(c["members"]) >= self.min_size]
        valid_clusters.sort(key=lambda c: len(c["members"]), reverse=True)

        results = []
        for cid, c in enumerate(valid_clusters[:top_clusters]):
            member_indices = c["members"]
            size = len(member_indices)
            share = size / n_samples

            top_terms = sorted(c["term_sum"].items(), key=lambda x: x[1], reverse=True)[:5]
            keywords = [t[0] for t in top_terms]
            if not keywords:
                keywords = ["general", "feedback"]

            # Representative exemplar
            exemplar = sample_texts[member_indices[0]]

            if sentiment_scores and len(sentiment_scores) == len(texts):
                avg_sent = sum(sentiment_scores[idx] for idx in member_indices) / size
            else:
                avg_sent = 0.0

            title = " & ".join(k.capitalize() for k in keywords[:3])

            results.append(
                NarrativeCluster(
                    cluster_id=cid + 1,
                    size=size,
                    share=round(share, 4),
                    keywords=keywords,
                    representative_text=exemplar[:200],
                    net_sentiment=round(avg_sent, 3),
                    thematic_title=title,
                )
            )

        return results
