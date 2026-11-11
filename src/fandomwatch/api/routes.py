"""Enterprise API endpoints for FandomWatch."""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from fandomwatch.config import settings
from fandomwatch.db import connect, get_or_create_title, iso, now_iso, parse_ts
from fandomwatch.fandom import conversation_share, fandom_report
from fandomwatch.metrics import export_metrics, HTTP_REQUESTS_TOTAL, ML_INFERENCE_LATENCY
from fandomwatch.ml.absa import AspectSentimentEngine
from fandomwatch.ml.agent import CrisisResponseAgent
from fandomwatch.ml.anomaly import BacklashDetector
from fandomwatch.ml.embeddings import DenseEmbedder, semantic_search
from fandomwatch.ml.forecasting import SentimentForecaster
from .schemas import (
    CommentIngestRequest,
    CrisisBriefResponse,
    ForecastResponse,
    HealthResponse,
    SemanticSearchRequest,
    TitleResponse,
)

router = APIRouter()


def get_db():
    conn = connect(settings.database_url, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


@router.get("/healthz", response_model=HealthResponse, tags=["Observability"])
@router.get("/livez", response_model=HealthResponse, tags=["Observability"])
@router.get("/readyz", response_model=HealthResponse, tags=["Observability"])
def health_check(db=Depends(get_db)):
    """Kubernetes liveness and readiness probe endpoint."""
    try:
        db.execute("SELECT 1").fetchone()
        db_status = "connected"
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unhealthy")
    return HealthResponse(status="ok", version="2.0.0", database=db_status)


@router.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    """Prometheus metrics scraping endpoint for Grafana and autoscalers."""
    body, content_type = export_metrics()
    return Response(content=body, media_type=content_type)


@router.get("/api/v1/titles", response_model=List[TitleResponse], tags=["Titles"])
def list_titles(db=Depends(get_db)):
    """Lists all monitored entertainment titles with aggregated comment counts and sentiment."""
    rows = db.execute("SELECT id, name, genre, studio, release_date FROM titles ORDER BY id").fetchall()
    t_ids = [r["id"] for r in rows]
    shares = conversation_share(db, t_ids) if t_ids else {}

    results = []
    for r in rows:
        tid = r["id"]
        c_stats = shares.get(tid, {})
        results.append(
            TitleResponse(
                id=tid,
                name=r["name"],
                genre=r["genre"],
                studio=r["studio"],
                release_date=r["release_date"],
                comments=c_stats.get("comments", 0),
                net_sentiment=c_stats.get("net_sentiment"),
            )
        )
    return results


@router.get("/api/v1/fandom/{title_id}", tags=["Analytics"])
def get_title_fandom_report(title_id: int, db=Depends(get_db)):
    """Retrieves full AI/ML analytics report: ABSA aspects, narrative clusters, backlash episodes, daily series."""
    row = db.execute("SELECT id FROM titles WHERE id = ?", (title_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Title not found")

    all_ids = [r["id"] for r in db.execute("SELECT id FROM titles").fetchall()]
    peer_ids = [i for i in all_ids if i != title_id]
    return fandom_report(db, title_id, peer_ids)


@router.get("/api/v1/fandom/{title_id}/forecast", response_model=ForecastResponse, tags=["Predictive ML"])
def forecast_sentiment_trajectory(
    title_id: int,
    horizon_days: int = Query(7, ge=1, le=30),
    db=Depends(get_db),
):
    """Generates 7-14 day Holt-Winters predictive trajectory for negative sentiment share and volume."""
    report = fandom_report(db, title_id)
    if not report.get("daily"):
        raise HTTPException(status_code=400, detail="Insufficient historical data for forecasting")

    daily = report["daily"]
    shares = [d["neg_share"] for d in daily]
    volumes = [d["n"] for d in daily]

    forecaster = SentimentForecaster()
    res = forecaster.fit_predict(shares, volumes, horizon=horizon_days)

    return ForecastResponse(
        title_id=title_id,
        trend_direction=res.trend_direction,
        alert_level=res.alert_level,
        days_to_threshold_breach=res.days_to_threshold_breach,
        projected_trajectory=[p.__dict__ for p in res.projected_points],
    )


@router.get("/api/v1/fandom/{title_id}/crisis-brief", response_model=CrisisBriefResponse, tags=["AI Agents"])
def generate_crisis_response_brief(title_id: int, db=Depends(get_db)):
    """Synthesizes an autonomous PR Crisis Response Brief with executive talking points and mitigation tactics."""
    t_row = db.execute("SELECT name FROM titles WHERE id = ?", (title_id,)).fetchone()
    if not t_row:
        raise HTTPException(status_code=404, detail="Title not found")

    rep = fandom_report(db, title_id)
    episodes = rep.get("backlash", [])
    if not episodes:
        # Generate baseline proactive brief
        severity = "watch"
        peak_share = rep.get("sentiment", {}).get("neg", 0.15)
        top_aspects = [a["aspect"] for a in rep.get("aspects", [])[:3]]
        narratives = [" / ".join(n["terms"]) for n in rep.get("narratives", [])[:2]]
    else:
        ep = episodes[0]
        severity = ep["severity"]
        peak_share = ep["peak_neg_share"]
        top_aspects = ep.get("top_aspects", [])
        narratives = [" / ".join(t) for t in ep.get("themes", [])]

    # Sample quotes from title
    quotes = [r["text"] for r in db.execute(
        "SELECT text FROM comments WHERE title_id = ? ORDER BY likes DESC LIMIT 5",
        (title_id,)
    ).fetchall()]

    agent = CrisisResponseAgent()
    brief = agent.generate_brief(
        title_name=t_row["name"],
        severity=severity,
        peak_share=peak_share,
        top_aspects=top_aspects,
        top_narratives=narratives,
        sample_quotes=quotes,
    )
    return CrisisBriefResponse(**brief.__dict__)


@router.post("/api/v1/fandom/{title_id}/search", tags=["Vector Search"])
def search_title_comments(
    title_id: int,
    req: SemanticSearchRequest,
    db=Depends(get_db),
):
    """Performs dense vector semantic search across comments of a specific title."""
    rows = db.execute("SELECT text FROM comments WHERE title_id = ? LIMIT 2000", (title_id,)).fetchall()
    docs = [r["text"] for r in rows]
    if not docs:
        return {"query": req.query, "matches": []}

    matches = semantic_search(req.query, docs, top_k=req.top_k)
    return {
        "query": req.query,
        "matches": [
            {"score": round(sim, 4), "text": doc}
            for _, sim, doc in matches
        ],
    }


@router.post("/api/v1/fandom/ingest", status_code=status.HTTP_201_CREATED, tags=["Ingestion"])
def ingest_comment(req: CommentIngestRequest, db=Depends(get_db)):
    """Ingests a social media comment idempotently with deduplication."""
    try:
        tid = get_or_create_title(db, req.title.strip())
        ts = iso(parse_ts(req.posted_at))
        db.execute(
            "INSERT INTO comments (title_id, platform, native_id, posted_at, text, likes) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT (platform, native_id) DO NOTHING",
            (tid, req.platform.lower(), req.comment_id, ts, req.text.strip(), req.likes),
        )
        db.commit()
        return {"status": "accepted", "title_id": tid}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
