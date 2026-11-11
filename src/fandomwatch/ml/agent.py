"""Autonomous PR & Brand Crisis Response AI Agent.
Synthesizes detected backlash incidents into actionable mitigation briefs and executive communication strategies."""
import json
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CrisisBrief:
    title: str
    severity: str
    risk_level: str
    executive_summary: str
    primary_friction_points: List[str]
    talking_points: List[str]
    immediate_actions: List[str]
    community_response_template: str


class CrisisResponseAgent:
    """Agent that creates structured PR and brand defense playbooks from fan backlash signals."""

    def __init__(self, llm_callable=None):
        self.llm = llm_callable

    def generate_brief(
        self,
        title_name: str,
        severity: str,
        peak_share: float,
        top_aspects: List[str],
        top_narratives: List[str],
        sample_quotes: List[str],
    ) -> CrisisBrief:
        """Synthesizes structured PR briefing and tactical response playbook."""
        # Check if an LLM is available
        if self.llm:
            prompt = (
                f"You are an elite Hollywood and Gaming Studio PR Crisis Manager. "
                f"A fan backlash has been detected for '{title_name}'.\n"
                f"- Severity: {severity.upper()}\n"
                f"- Peak Negative Share: {peak_share:.1%}\n"
                f"- Top Troubled Aspects: {', '.join(top_aspects)}\n"
                f"- Recurring Narrative Themes: {'; '.join(top_narratives)}\n"
                f"- Sample Fan Quotes: {json.dumps(sample_quotes)}\n\n"
                "Provide an executive crisis response brief in JSON with the exact keys: "
                "['executive_summary', 'primary_friction_points', 'talking_points', 'immediate_actions', 'community_response_template']."
            )
            try:
                raw = self.llm(prompt, max_tokens=1000)
                # Attempt to extract JSON from markdown if needed
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(raw[start:end])
                    return CrisisBrief(
                        title=title_name,
                        severity=severity,
                        risk_level="CRITICAL RISK" if severity == "critical" else "ELEVATED RISK",
                        executive_summary=data.get("executive_summary", ""),
                        primary_friction_points=data.get("primary_friction_points", []),
                        talking_points=data.get("talking_points", []),
                        immediate_actions=data.get("immediate_actions", []),
                        community_response_template=data.get("community_response_template", ""),
                    )
            except Exception:
                pass  # Fall back to deterministic playbook generator

        # Deterministic domain-specific crisis response playbook generator
        aspect_str = ", ".join(top_aspects) if top_aspects else "creative execution"
        exec_summary = (
            f"Fan sentiment for '{title_name}' suffered an anomalous contraction, reaching a peak "
            f"negative share of {peak_share:.1%}. Negative discourse is disproportionately concentrated "
            f"around {aspect_str}. Immediate narrative steering is recommended."
        )

        frictions = [
            f"Severe negative sentiment cluster targeting {a.capitalize()}." for a in top_aspects[:3]
        ] or ["High concentration of overall fan dissatisfaction."]

        actions = [
            "Align studio spokespeople on unified talking points prior to upcoming press engagements.",
            f"Pause high-frequency promotional ad spend emphasizing {top_aspects[0] if top_aspects else 'trailers'}.",
            "Deploy transparent behind-the-scenes material to address fan concerns with authentic context.",
            "Monitor hourly social momentum on YouTube and Reddit for escalation triggers.",
        ]

        talking_points = [
            f"We deeply value the passion of our community and are actively listening to your thoughts on {title_name}.",
            "Our creative team worked tirelessly to bring this vision to life, and we are excited for fans to experience the full story in context.",
            "We remain dedicated to delivering an unforgettable experience that honors fan expectations.",
        ]

        comm_template = (
            f"To our incredible fans: We hear you, and we appreciate the honest feedback regarding {title_name}. "
            f"Every story has many layers, and we can't wait for you to see how everything comes together. "
            f"Thank you for your ongoing passion and support."
        )

        return CrisisBrief(
            title=title_name,
            severity=severity,
            risk_level="CRITICAL RISK" if severity == "critical" else "ELEVATED RISK",
            executive_summary=exec_summary,
            primary_friction_points=frictions,
            talking_points=talking_points,
            immediate_actions=actions,
            community_response_template=comm_template,
        )
