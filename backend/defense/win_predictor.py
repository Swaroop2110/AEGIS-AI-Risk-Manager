"""Agent 3: evidence-completeness win probability and cost-benefit model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import dispute_config

from .evidence_aggregator import EvidenceBundle


@dataclass
class DefenseDecision:
    win_probability: float
    recommended_action: str
    cost_benefit: dict[str, Any]


class WinProbabilityPredictor:
    """A transparent baseline before dispute-outcome labels are available."""

    def predict(self, bundle: EvidenceBundle, strategy: dict[str, Any]) -> DefenseDecision:
        authentication = bundle.sections["authentication"]
        delivery = bundle.sections["delivery"]
        history = bundle.sections["customer_history"]
        probability = 0.20 + bundle.completeness * 0.40
        if authentication.get("otp_verified") or authentication.get("eci_value") == "05":
            probability += 0.12
        if delivery.get("signature_url") or bundle.transaction.delivery_signed:
            probability += 0.14
        if delivery.get("tracking_url") or bundle.transaction.delivery_tracking_id:
            probability += 0.08
        if (history.get("dispute_rate") or 0) > 0.03:
            probability += 0.07
        if strategy["missing_evidence"]:
            probability -= min(len(strategy["missing_evidence"]) * 0.04, 0.16)
        probability = round(max(0.02, min(0.98, probability)), 4)

        if probability >= dispute_config.auto_defend_threshold:
            action = "auto_defend"
        elif probability >= dispute_config.review_threshold:
            action = "review"
        else:
            action = "accept"

        amount = bundle.transaction.amount or 0
        expected_recovery = int(amount * probability)
        expected_value = int(expected_recovery - (1 - probability) * dispute_config.arbitration_fee)
        return DefenseDecision(
            win_probability=probability,
            recommended_action=action,
            cost_benefit={
                "transaction_amount": amount,
                "expected_recovery": expected_recovery,
                "arbitration_fee": dispute_config.arbitration_fee,
                "expected_value": expected_value,
            },
        )
