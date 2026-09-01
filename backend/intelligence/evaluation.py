"""Honest, cost-aware evaluation for stored AEGIS scores."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import model_config
from database.models import RiskScore, Transaction


def evaluate_stored_scores(db: Session, threshold: float | None = None) -> dict[str, Any]:
    """Evaluate the latest risk score of every labelled transaction."""
    threshold = model_config.high_risk_threshold if threshold is None else threshold
    latest_scores = (
        db.query(RiskScore.transaction_id, func.max(RiskScore.id).label("score_id"))
        .group_by(RiskScore.transaction_id)
        .subquery()
    )
    rows = (
        db.query(Transaction, RiskScore)
        .join(latest_scores, Transaction.id == latest_scores.c.transaction_id)
        .join(RiskScore, RiskScore.id == latest_scores.c.score_id)
        .all()
    )
    if not rows:
        return {
            "scored_transactions": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "false_positive_rate": 0.0,
            "confusion_matrix": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
            "cost_analysis": {"fraud_prevented_paise": 0, "false_positive_cost_paise": 0, "missed_fraud_cost_paise": 0, "net_impact_paise": 0},
        }

    tp = fp = tn = fn = 0
    fraud_prevented = false_positive_cost = missed_fraud_cost = 0
    latencies: list[float] = []
    for transaction, score in rows:
        predicted_fraud = (score.aegis_score or 0.0) >= threshold
        actual_fraud = bool(transaction.is_fraud)
        amount = transaction.amount or 0
        if predicted_fraud and actual_fraud:
            tp += 1
            fraud_prevented += int(amount * 2.5)
        elif predicted_fraud:
            fp += 1
            false_positive_cost += amount
        elif actual_fraud:
            fn += 1
            missed_fraud_cost += int(amount * 2.5)
        else:
            tn += 1
        latencies.append((score.l1_latency_ms or 0) + (score.l2_latency_ms or 0))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return {
        "scored_transactions": len(rows),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "avg_score_latency_ms": round(sum(latencies) / len(latencies), 3),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "cost_analysis": {
            "fraud_prevented_paise": fraud_prevented,
            "false_positive_cost_paise": false_positive_cost,
            "missed_fraud_cost_paise": missed_fraud_cost,
            "net_impact_paise": fraud_prevented - false_positive_cost - missed_fraud_cost,
        },
    }
