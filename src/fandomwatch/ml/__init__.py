"""Enterprise AI/ML Package for FandomWatch: ABSA, Embeddings, Clustering, Anomaly & Forecasting."""

from .embeddings import DenseEmbedder, cosine_similarity, semantic_search
from .absa import AspectSentimentEngine, AspectResult
from .clustering import SemanticClusterer, NarrativeCluster
from .anomaly import BacklashDetector, AnomalyEpisode
from .forecasting import SentimentForecaster, ForecastResult
from .agent import CrisisResponseAgent

__all__ = [
    "DenseEmbedder",
    "cosine_similarity",
    "semantic_search",
    "AspectSentimentEngine",
    "AspectResult",
    "SemanticClusterer",
    "NarrativeCluster",
    "BacklashDetector",
    "AnomalyEpisode",
    "SentimentForecaster",
    "ForecastResult",
    "CrisisResponseAgent",
]
