"""Fast, explainable first-layer transaction risk scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import exp, log1p
from pathlib import Path
from statistics import mean, pstdev
from time import perf_counter
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from config import MODELS_DIR
from database.models import Customer, Transaction


MODEL_FEATURE_ORDER = (
    "amount_log",
    "hour",
    "account_age_days",
    "txn_velocity_1h",
    "txn_velocity_24h",
    "is_new_device",
    "amount_zscore",
    "ip_fraud_rate",
    "geo_mismatch",
)


@dataclass
class L1Score:
    """The fast-path result and the signals used to produce it."""

    rule_score: float
    model_score: float
    combined_score: float
    triggers: list[dict[str, Any]]
    top_features: list[dict[str, Any]]
    features: dict[str, float]
    latency_ms: float


class LightGBMBaseline:
    """Optional LightGBM inference with a deterministic fallback before training.

    Phase 1 creates labelled synthetic records, but a model artifact is not
    assumed to exist when the API first starts. The fallback keeps scoring
    deterministic and exposes the same feature contract used by the trained
    LightGBM model once one is saved under ``data/models``.
    """

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or MODELS_DIR / "l1_lightgbm.txt"
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            return
        try:
            import lightgbm as lgb

            self._model = lgb.Booster(model_file=str(self.model_path))
        except (ImportError, OSError, ValueError):
            self._model = None

    def predict(self, features: dict[str, float]) -> float:
        if self._model is not None:
            values = [[features[name] for name in MODEL_FEATURE_ORDER]]
            return float(self._model.predict(values)[0])

        linear_score = (
            -3.0
            + min(features["txn_velocity_1h"], 20) * 0.18
            + min(features["amount_zscore"], 6) * 0.28
            + features["is_new_device"] * 0.9
            + features["geo_mismatch"] * 0.75
            + min(features["ip_fraud_rate"], 1.0) * 1.5
        )
        return 1.0 / (1.0 + exp(-linear_score))


class L1RiskEngine:
    """Deterministic checks plus LightGBM-compatible feature extraction."""

    def __init__(self, db: Session, model: Optional[LightGBMBaseline] = None):
        self.db = db
        self.model = model or LightGBMBaseline()

    def score(self, transaction: Transaction, customer: Optional[Customer]) -> L1Score:
        started = perf_counter()
        now = transaction.created_at or datetime.utcnow()
        velocity_1h = self._transaction_count(transaction, now - timedelta(hours=1))
        velocity_24h = self._transaction_count(transaction, now - timedelta(hours=24))
        amount_zscore = self._amount_zscore(transaction, now)
        ip_fraud_rate = self._ip_fraud_rate(transaction.ip_address)
        is_new_device = self._is_new_device(transaction, customer)
        geo_mismatch = self._geo_mismatch(transaction, customer)

        features = {
            "amount_log": log1p(max(transaction.amount or 0, 0)),
            "hour": float(now.hour),
            "account_age_days": float(customer.account_age_days or 0) if customer else 0.0,
            "txn_velocity_1h": float(velocity_1h),
            "txn_velocity_24h": float(velocity_24h),
            "is_new_device": float(is_new_device),
            "amount_zscore": float(amount_zscore),
            "ip_fraud_rate": float(ip_fraud_rate),
            "geo_mismatch": float(geo_mismatch),
        }
        triggers = self._evaluate_rules(features, transaction, ip_fraud_rate)
        rule_score = min(1.0, sum(trigger["weight"] for trigger in triggers))
        model_score = self.model.predict(features)
        # 70% rule + 30% model: deterministic rules are highly reliable signals
        combined_score = min(1.0, 0.70 * rule_score + 0.30 * model_score)

        contributions = {
            "txn_velocity_1h": min(features["txn_velocity_1h"] / 10, 1.0),
            "amount_deviation": min(features["amount_zscore"] / 4, 1.0),
            "new_device": features["is_new_device"] * 0.8,
            "geo_mismatch": features["geo_mismatch"] * 0.7,
            "ip_fraud_history": min(features["ip_fraud_rate"], 1.0),
        }
        top_features = [
            {"feature": name, "contribution": round(value, 3)}
            for name, value in sorted(contributions.items(), key=lambda item: item[1], reverse=True)
            if value > 0
        ][:5]

        return L1Score(
            rule_score=round(rule_score, 4),
            model_score=round(model_score, 4),
            combined_score=round(combined_score, 4),
            triggers=triggers,
            top_features=top_features,
            features=features,
            latency_ms=round((perf_counter() - started) * 1_000, 3),
        )

    def _transaction_count(self, transaction: Transaction, since: datetime) -> int:
        conditions = []
        if transaction.device_id:
            conditions.append(Transaction.device_id == transaction.device_id)
        if transaction.customer_id:
            conditions.append(Transaction.customer_id == transaction.customer_id)
        if not conditions:
            return 0
        return int(
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.created_at >= since, or_(*conditions))
            .scalar()
            or 0
        )

    def _amount_zscore(self, transaction: Transaction, now: datetime) -> float:
        amounts = [
            value[0]
            for value in (
                self.db.query(Transaction.amount)
                .filter(
                    Transaction.customer_id == transaction.customer_id,
                    Transaction.created_at >= now - timedelta(days=90),
                    Transaction.status == "captured",
                )
                .limit(100)
                .all()
            )
            if value[0] is not None
        ]
        if len(amounts) < 5:
            return 0.0
        deviation = pstdev(amounts)
        if deviation == 0:
            return 0.0
        return min(abs((transaction.amount - mean(amounts)) / deviation), 10.0)

    def _ip_fraud_rate(self, ip_address: Optional[str]) -> float:
        if not ip_address:
            return 0.0
        total = int(
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.ip_address == ip_address)
            .scalar()
            or 0
        )
        if total == 0:
            return 0.0
        fraud = int(
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.ip_address == ip_address, Transaction.is_fraud.is_(True))
            .scalar()
            or 0
        )
        return fraud / total

    @staticmethod
    def _is_new_device(transaction: Transaction, customer: Optional[Customer]) -> bool:
        return bool(
            customer
            and customer.primary_device_id
            and transaction.device_id
            and customer.primary_device_id != transaction.device_id
        )

    @staticmethod
    def _geo_mismatch(transaction: Transaction, customer: Optional[Customer]) -> bool:
        if transaction.geo_ip_match is False:
            return True
        return bool(customer and transaction.ip_city and transaction.ip_city != customer.city)

    @staticmethod
    def _evaluate_rules(
        features: dict[str, float], transaction: Transaction, ip_fraud_rate: float
    ) -> list[dict[str, Any]]:
        triggers: list[dict[str, Any]] = []

        def add(rule: str, weight: float, detail: str) -> None:
            triggers.append({"rule": rule, "weight": weight, "detail": detail})

        if features["txn_velocity_1h"] >= 10:
            add("velocity_burst", 0.65, "10 or more related transactions in the last hour")
        elif features["txn_velocity_1h"] >= 5:
            add("elevated_velocity", 0.35, "5 or more related transactions in the last hour")
        if features["amount_zscore"] >= 3:
            add("amount_anomaly", 0.30, "amount is more than 3 standard deviations from customer history")
        if features["is_new_device"]:
            add("new_device", 0.20, "device differs from the customer's known device")
        if features["geo_mismatch"]:
            add("geo_mismatch", 0.20, "IP location is inconsistent with the customer profile")
        if ip_fraud_rate >= 0.2:
            add("fraud_linked_ip", 0.55, "IP address is linked to prior fraudulent transactions")
        if transaction.created_at and transaction.created_at.hour < 5:
            add("unusual_hour", 0.10, "transaction occurred during a low-activity time window")
        return triggers
