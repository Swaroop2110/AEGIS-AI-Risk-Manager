"""Chargeback likelihood and time-to-dispute estimates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from database.models import Customer, Transaction


@dataclass
class ChargebackPrediction:
    probability: float
    predicted_days: int


class ChargebackPredictor:
    """Interpretable survival-style baseline for completed transactions.

    This baseline is intentionally deterministic until the Phase 1 labels are
    used to fit a Cox model. It exposes both the probability and time-to-event
    interface required by the scoring API and the later proactive-alert flow.
    """

    def predict(
        self, transaction: Transaction, customer: Optional[Customer], risk_score: float
    ) -> ChargebackPrediction:
        probability = risk_score * 0.62
        if transaction.payment_method in {"credit_card", "debit_card"}:
            probability += 0.05
        if customer and customer.dispute_count:
            probability += min(customer.dispute_count * 0.06, 0.20)
        if transaction.delivery_status == "delivered" and transaction.delivery_signed:
            probability -= 0.08
        if transaction.auth_type == "3ds" and transaction.eci_indicator == "05":
            probability -= 0.05

        probability = max(0.01, min(0.98, probability))
        predicted_days = int(max(7, min(90, round(90 - probability * 70))))
        return ChargebackPrediction(round(probability, 4), predicted_days)
