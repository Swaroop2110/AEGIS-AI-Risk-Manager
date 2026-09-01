"""Counterfactual risk explanations for the AEGIS scoring response."""

from __future__ import annotations

from typing import Any, Optional

from database.models import Customer, Transaction

from .l1_engine import L1Score
from .l2_graph_engine import L2Score


class CausalExplanationEngine:
    """Produce actionable explanations from causally meaningful risk signals.

    The feature graph deliberately separates mutable safeguards (known-device
    confirmation, step-up authentication, delivery proof) from observational
    signals such as amount and velocity. This gives the API a stable
    counterfactual contract while a data-trained DoWhy model is added later.
    """

    def explain(
        self,
        transaction: Transaction,
        customer: Optional[Customer],
        l1: L1Score,
        l2: Optional[L2Score],
        final_score: float,
    ) -> tuple[dict[str, Any], str]:
        factors: list[dict[str, Any]] = []
        features = l1.features

        def add(name: str, value: str, contribution: float, intervention: str) -> None:
            factors.append({
                "factor": name,
                "observed": value,
                "contribution": round(contribution, 3),
                "intervention": intervention,
            })

        if features["txn_velocity_1h"] >= 5:
            add(
                "transaction_velocity",
                f"{int(features['txn_velocity_1h'])} related transactions in the last hour",
                min(features["txn_velocity_1h"] / 10, 1.0),
                "delay or step up additional transactions until the velocity window normalizes",
            )
        if features["amount_zscore"] >= 3:
            add(
                "amount_deviation",
                f"{features['amount_zscore']:.1f} standard deviations above normal",
                min(features["amount_zscore"] / 5, 1.0),
                "obtain stronger authentication for an unusually large purchase",
            )
        if features["is_new_device"]:
            add(
                "device_trust",
                "device does not match the customer's established device",
                0.7,
                "complete device binding or step-up authentication before approval",
            )
        if features["geo_mismatch"]:
            add(
                "geographic_consistency",
                "IP location conflicts with the customer profile",
                0.6,
                "verify the customer's current location and payment authentication",
            )
        if features["ip_fraud_rate"] > 0:
            add(
                "network_reputation",
                f"{features['ip_fraud_rate']:.0%} of observed IP transactions are fraudulent",
                min(features["ip_fraud_rate"], 1.0),
                "block or challenge traffic from this network until manually reviewed",
            )
        if l2 and l2.ring_detected:
            add(
                "ring_connectivity",
                "shared entity pattern links this transaction to a suspected abuse ring",
                l2.ring_score,
                "block the linked entity set and review the ring as a group",
            )

        factors.sort(key=lambda item: item["contribution"], reverse=True)
        top_factors = factors[:5]
        if not top_factors:
            counterfactual = "Transaction is low risk. No additional verification is needed."
        else:
            primary = top_factors[0]
            reduced_score = max(0.02, final_score - primary["contribution"] * 0.45)
            counterfactual = (
                f"If {primary['intervention']}, the estimated risk could fall from "
                f"{final_score:.0%} to approximately {reduced_score:.0%}."
            )

        explanation = {
            "top_factors": top_factors,
            "causal_graph": {
                "risk_inputs": [factor["factor"] for factor in top_factors],
                "outcome": "transaction_fraud_or_chargeback_risk",
                "customer_context_available": customer is not None,
            },
        }
        return explanation, counterfactual
