"""Time-Series Forecasting Engine for Audience Sentiment & Volume.
Applies Holt-Winters exponential trend smoothing to project 7-14 day trajectories and early warning risks."""
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass
class ForecastPoint:
    step: int
    projected_negative_share: float
    lower_ci95: float
    upper_ci95: float
    projected_volume: int


@dataclass
class ForecastResult:
    trend_direction: str  # "escalating", "de-escalating", "stable"
    projected_points: List[ForecastPoint]
    days_to_threshold_breach: int  # -1 if no breach projected
    alert_level: str  # "green", "amber", "red"


class SentimentForecaster:
    """Double Exponential Smoothing (Holt's Linear Trend) time-series forecaster."""

    def __init__(self, alpha: float = 0.35, beta: float = 0.15):
        self.alpha = alpha  # Level smoothing factor
        self.beta = beta    # Trend smoothing factor

    def fit_predict(
        self,
        historical_shares: Sequence[float],
        historical_volumes: Sequence[int],
        horizon: int = 7,
        critical_share_threshold: float = 0.40,
    ) -> ForecastResult:
        """Projects future sentiment trajectory and flags impending risk thresholds."""
        n = len(historical_shares)
        if n < 3:
            # Fallback for short histories
            last_share = historical_shares[-1] if historical_shares else 0.25
            last_vol = historical_volumes[-1] if historical_volumes else 50
            pts = [
                ForecastPoint(
                    step=i + 1,
                    projected_negative_share=round(last_share, 3),
                    lower_ci95=round(max(0.0, last_share - 0.1), 3),
                    upper_ci95=round(min(1.0, last_share + 0.1), 3),
                    projected_volume=int(last_vol),
                )
                for i in range(horizon)
            ]
            return ForecastResult("stable", pts, -1, "green")

        # Holt's linear trend on negative share
        level = historical_shares[0]
        trend = historical_shares[1] - historical_shares[0]
        residuals = []

        for t in range(1, n):
            val = historical_shares[t]
            pred = level + trend
            residuals.append(val - pred)
            prev_level = level
            level = self.alpha * val + (1 - self.alpha) * (level + trend)
            trend = self.beta * (level - prev_level) + (1 - self.beta) * trend

        # Variance of residuals for prediction interval estimation
        rmse = (sum(r * r for r in residuals) / len(residuals)) ** 0.5 if residuals else 0.05
        avg_vol = sum(historical_volumes) / len(historical_volumes)

        points = []
        breach_step = -1
        for h in range(1, horizon + 1):
            y_hat = max(0.0, min(1.0, level + h * trend))
            margin = 1.96 * rmse * (h ** 0.5)
            lo = max(0.0, y_hat - margin)
            hi = min(1.0, y_hat + margin)

            if y_hat >= critical_share_threshold and breach_step == -1:
                breach_step = h

            points.append(
                ForecastPoint(
                    step=h,
                    projected_negative_share=round(y_hat, 4),
                    lower_ci95=round(lo, 4),
                    upper_ci95=round(hi, 4),
                    projected_volume=int(round(avg_vol)),
                )
            )

        if trend > 0.015:
            trend_dir = "escalating"
            alert = "red" if breach_step != -1 else "amber"
        elif trend < -0.015:
            trend_dir = "de-escalating"
            alert = "green"
        else:
            trend_dir = "stable"
            alert = "amber" if points[0].projected_negative_share >= 0.30 else "green"

        return ForecastResult(
            trend_direction=trend_dir,
            projected_points=points,
            days_to_threshold_breach=breach_step,
            alert_level=alert,
        )
