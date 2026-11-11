import unittest
from fandomwatch.ml.embeddings import DenseEmbedder, cosine_similarity, semantic_search
from fandomwatch.ml.absa import AspectSentimentEngine, AspectResult
from fandomwatch.ml.clustering import SemanticClusterer
from fandomwatch.ml.anomaly import BacklashDetector
from fandomwatch.ml.forecasting import SentimentForecaster
from fandomwatch.ml.agent import CrisisResponseAgent


class TestMLSuite(unittest.TestCase):
    def test_embeddings_and_cosine(self):
        embedder = DenseEmbedder(dim=64)
        v1 = embedder.embed_text("The movie soundtrack and music was incredible!")
        v2 = embedder.embed_text("Awesome music score and great songs!")
        v3 = embedder.embed_text("Overpriced popcorn and greedy ticket pricing.")

        self.assertEqual(len(v1), 64)
        self.assertAlmostEqual(cosine_similarity(v1, v1), 1.0, places=4)
        sim_related = cosine_similarity(v1, v2)
        sim_unrelated = cosine_similarity(v1, v3)
        self.assertGreater(sim_related, sim_unrelated)

    def test_semantic_search(self):
        docs = [
            "Loved the amazing visual effects and cinematography.",
            "The ticket prices are far too expensive and a scam.",
            "Hilarious jokes and comedy throughout the entire runtime."
        ]
        results = semantic_search("budget and ticket price ripoff", docs, top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 1)  # Index 1 is the ticket price doc

    def test_absa_sentence_level(self):
        engine = AspectSentimentEngine()
        text = "The acting by the lead was brilliant! The story was a boring mess. The CGI visuals look nice."
        aspects = engine.analyze_comment(text)

        self.assertIn("acting", aspects)
        self.assertIn("pos", aspects["acting"])
        self.assertIn("story", aspects)
        self.assertIn("neg", aspects["story"])

        aggregated = engine.aggregate_aspects([text])
        act_res = next(a for a in aggregated if a.aspect == "acting")
        self.assertEqual(act_res.net_sentiment, 1.0)
        story_res = next(a for a in aggregated if a.aspect == "story")
        self.assertEqual(story_res.net_sentiment, -1.0)

    def test_clustering_narratives(self):
        clusterer = SemanticClusterer(similarity_threshold=0.25, min_cluster_size=2)
        comments = [
            "the ticket price is too expensive",
            "ticket prices are total greed and ripoff",
            "overpriced tickets everywhere",
            "the cinematography and visual effects are breathtaking",
            "gorgeous visuals and stunning cinematography",
        ]
        clusters = clusterer.cluster(comments, top_clusters=2)
        self.assertGreaterEqual(len(clusters), 1)
        # Verify cluster structure
        for c in clusters:
            self.assertGreater(c.size, 0)
            self.assertTrue(len(c.keywords) > 0)

    def test_backlash_anomaly_detection(self):
        detector = BacklashDetector(min_day_volume=20, min_negative_count=10, z_threshold=3.0)
        # Create 10 calm days
        records = []
        for d in range(1, 11):
            date_str = f"2026-09-{d:02d}T12:00:00Z"
            for _ in range(25):
                records.append((date_str, "neg" if _ < 4 else "pos", 0))

        # Calm check
        self.assertEqual(detector.detect_episodes(records), [])

        # Add 2 storm days with 80% negative share
        for d in (11, 12):
            date_str = f"2026-09-{d:02d}T12:00:00Z"
            for _ in range(30):
                records.append((date_str, "neg" if _ < 24 else "pos", 0))

        episodes = detector.detect_episodes(records)
        self.assertEqual(len(episodes), 1)
        ep = episodes[0]
        self.assertEqual(ep.start_date, "2026-09-11")
        self.assertEqual(ep.end_date, "2026-09-12")
        self.assertIn(ep.severity, ("high", "critical"))
        self.assertGreater(ep.risk_score, 60.0)

    def test_sentiment_forecaster(self):
        forecaster = SentimentForecaster(alpha=0.4, beta=0.2)
        shares = [0.15, 0.18, 0.22, 0.28, 0.35, 0.42]
        vols = [100, 110, 105, 120, 130, 140]

        res = forecaster.fit_predict(shares, vols, horizon=7, critical_share_threshold=0.45)
        self.assertEqual(res.trend_direction, "escalating")
        self.assertEqual(len(res.projected_points), 7)
        self.assertIn(res.alert_level, ("amber", "red"))

    def test_crisis_response_agent(self):
        agent = CrisisResponseAgent()
        brief = agent.generate_brief(
            title_name="Steel Tide",
            severity="critical",
            peak_share=0.81,
            top_aspects=["casting", "price"],
            top_narratives=["ticket price greed", "recast controversy"],
            sample_quotes=["Ticket prices are a greedy ripoff", "Recasting the lead ruined it"],
        )
        self.assertEqual(brief.title, "Steel Tide")
        self.assertEqual(brief.severity, "critical")
        self.assertTrue(len(brief.immediate_actions) > 0)
        self.assertTrue(len(brief.talking_points) > 0)
        self.assertIn("Steel Tide", brief.executive_summary)


if __name__ == "__main__":
    unittest.main()
