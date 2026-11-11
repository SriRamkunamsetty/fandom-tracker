"""Production Anomaly & Backlash Detection Engine.
Employs sliding-window robust statistics, MAD scaling, and multi-day incident coalescing."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from fandomwatch.stats import robust_z


@dataclass
class AnomalyEpisode:
    episode_id: int
    severity: str  # "watch", "high", "critical"
    risk_score: float  # 0 to 100
    start_date: str
    end_date: str
    peak_date: str
    duration_days: int
    peak_negative_share: float
    total_negative_volume: int
    total_comment_volume: int
    outlier_z_score: float
    primary_aspects: List[str]
    narrative_keywords: List[str]
    summary: str


class BacklashDetector:
    """Robust statistical change-point & backlash incident detector."""

    def __init__(
        self,
        min_day_volume: int = 20,
        min_negative_count: int = 10,
        min_negative_share: float = 0.35,
        z_threshold: float = 3.5,
        min_history_days: int = 6,
    ):
        self.min_day_vol = min_day_volume
        self.min_neg = min_negative_count
        self.min_neg_share = min_negative_share
        self.z_thresh = z_threshold
        self.min_history = min_history_days

    def detect_episodes(
        self,
        daily_records: Sequence[Tuple[str, str, int]],  # (posted_at_iso, sentiment_label, likes)
        aspect_analyzer=None,
    ) -> List[AnomalyEpisode]:
        """Detects and characterizes anomalous backlash periods from timeline records."""
        # 1. Bucket daily stats
        days: Dict[str, List[int]] = defaultdict(lambda: [0, 0])  # date -> [total, neg_count]

        for ts, label, _ in daily_records:
            d = ts[:10]
            days[d][0] += 1
            if label == "neg":
                days[d][1] += 1

        usable_days = sorted(
            [(d, counts[0], counts[1], counts[1] / counts[0])
             for d, counts in days.items() if counts[0] >= self.min_day_vol],
            key=lambda x: x[0]
        )

        # Baseline stability requirement: at least 6 usable days required to avoid false positives
        if len(usable_days) < self.min_history:
            return []

        shares = [u[3] for u in usable_days]
        zs = robust_z(shares, floor=0.05)

        # 2. Identify candidate anomaly days
        flagged_indices = []
        for i, (z, u) in enumerate(zip(zs, usable_days)):
            date, total_n, neg_n, neg_share = u
            if (
                z >= self.z_thresh
                and neg_share >= self.min_neg_share
                and neg_n >= self.min_neg
            ):
                flagged_indices.append(i)

        if not flagged_indices:
            return []

        # 3. Merge contiguous days into cohesive episodes
        episodes_idx: List[List[int]] = []
        current: List[int] = []

        for idx in flagged_indices:
            if current and idx != current[-1] + 1:
                episodes_idx.append(current)
                current = []
            current.append(idx)
        if current:
            episodes_idx.append(current)

        # 4. Synthesize incident analysis
        episodes: List[AnomalyEpisode] = []
        for eid, group in enumerate(episodes_idx, start=1):
            start_d = usable_days[group[0]][0]
            end_d = usable_days[group[-1]][0]

            peak_idx = max(group, key=lambda i: usable_days[i][3])
            peak_d = usable_days[peak_idx][0]
            peak_share = usable_days[peak_idx][3]
            peak_z = zs[peak_idx]

            tot_neg = sum(usable_days[i][2] for i in group)
            tot_vol = sum(usable_days[i][1] for i in group)
            duration = len(group)

            # Severity classification
            if peak_share >= 0.60 and tot_neg >= 50:
                severity = "critical"
                risk_score = min(100.0, 75.0 + peak_share * 25.0)
            elif peak_share >= 0.50:
                severity = "high"
                risk_score = min(85.0, 50.0 + peak_share * 35.0)
            else:
                severity = "watch"
                risk_score = min(60.0, 30.0 + peak_share * 30.0)

            summary = (
                f"Backlash incident [{severity.upper()}] from {start_d} to {end_d}. "
                f"Peak negative share reached {peak_share:.1%} on {peak_d} with {tot_neg} negative comments "
                f"(Outlier z-score: {peak_z:.1f}σ)."
            )

            episodes.append(
                AnomalyEpisode(
                    episode_id=eid,
                    severity=severity,
                    risk_score=round(risk_score, 1),
                    start_date=start_d,
                    end_date=end_d,
                    peak_date=peak_d,
                    duration_days=duration,
                    peak_negative_share=round(peak_share, 4),
                    total_negative_volume=tot_neg,
                    total_comment_volume=tot_vol,
                    outlier_z_score=round(peak_z, 2),
                    primary_aspects=[],
                    narrative_keywords=[],
                    summary=summary,
                )
            )

        return episodes
