import os
import unittest
from fastapi.testclient import TestClient

from fandomwatch.api import create_app
from fandomwatch.config import settings
from fandomwatch.db import connect
from fandomwatch.sample_data import seed_all

TEST_DB = "test_fandom_api.db"


class TestEnterpriseAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings.database_url = f"sqlite:///{TEST_DB}"
        conn = connect(settings.database_url)
        seed_all(conn)
        conn.close()

        cls.app = create_app()
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass

    def test_health_endpoints(self):
        for endpoint in ("/healthz", "/livez", "/readyz"):
            resp = self.client.get(endpoint)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["version"], "2.0.0")

    def test_metrics_endpoint(self):
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("fandom", resp.text)

    def test_titles_and_fandom_report(self):
        resp = self.client.get("/api/v1/titles")
        self.assertEqual(resp.status_code, 200)
        titles = resp.json()
        self.assertIsInstance(titles, list)
        self.assertGreater(len(titles), 0)

        tid = titles[0]["id"]
        rep_resp = self.client.get(f"/api/v1/fandom/{tid}")
        self.assertEqual(rep_resp.status_code, 200)
        rep = rep_resp.json()
        self.assertIn("sentiment", rep)
        self.assertIn("aspects", rep)

    def test_ingest_and_search(self):
        # Ingest comment
        payload = {
            "title": "Astra Test",
            "comment_id": "api_c1",
            "posted_at": "2026-09-01T12:00:00Z",
            "text": "The music soundtrack was magnificent and beautiful!",
            "likes": 12,
            "platform": "youtube",
        }
        ingest_resp = self.client.post("/api/v1/fandom/ingest", json=payload)
        self.assertEqual(ingest_resp.status_code, 201)
        data = ingest_resp.json()
        self.assertEqual(data["status"], "accepted")
        tid = data["title_id"]

        # Search comment
        search_resp = self.client.post(
            f"/api/v1/fandom/{tid}/search",
            json={"query": "music and soundtrack songs", "top_k": 2},
        )
        self.assertEqual(search_resp.status_code, 200)
        s_data = search_resp.json()
        self.assertEqual(len(s_data["matches"]), 1)
        self.assertIn("music", s_data["matches"][0]["text"])

    def test_forecast_and_crisis_brief(self):
        # Seed Steel Tide (ID 2 in seed data)
        resp_titles = self.client.get("/api/v1/titles")
        steel_tide = next((t for t in resp_titles.json() if "Steel" in t["name"]), None)
        self.assertIsNotNone(steel_tide)
        tid = steel_tide["id"]

        # Forecast
        f_resp = self.client.get(f"/api/v1/fandom/{tid}/forecast?horizon_days=7")
        self.assertEqual(f_resp.status_code, 200)
        f_data = f_resp.json()
        self.assertIn("trend_direction", f_data)
        self.assertEqual(len(f_data["projected_trajectory"]), 7)

        # Crisis Brief
        c_resp = self.client.get(f"/api/v1/fandom/{tid}/crisis-brief")
        self.assertEqual(c_resp.status_code, 200)
        c_data = c_resp.json()
        self.assertEqual(c_data["title"], steel_tide["name"])
        self.assertTrue(len(c_data["immediate_actions"]) > 0)


if __name__ == "__main__":
    unittest.main()
