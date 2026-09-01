"""Model-training utilities for Phase 2 synthetic data."""

from __future__ import annotations

from collections import defaultdict
from math import log1p
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from sqlalchemy.orm import Session

from config import MODELS_DIR, model_config
from database.models import Customer, Transaction

from .l1_engine import MODEL_FEATURE_ORDER


def train_l1_lightgbm(db: Session, model_path: Path | None = None) -> dict[str, Any]:
    """Fit and save the L1 LightGBM baseline from generated labelled records."""
    try:
        import lightgbm as lgb
        from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError as error:
        raise RuntimeError("Install the ML dependencies from requirements.txt before training") from error

    rows = (
        db.query(Transaction, Customer)
        .join(Customer, Transaction.customer_id == Customer.id)
        .order_by(Transaction.created_at)
        .all()
    )
    if len(rows) < 20:
        raise ValueError("At least 20 generated transactions are required to train the L1 model")

    # ---------- Pre-compute IP fraud rates ----------
    ip_totals: defaultdict[str, int] = defaultdict(int)
    ip_fraud: defaultdict[str, int] = defaultdict(int)
    for transaction, _ in rows:
        if transaction.ip_address:
            ip_totals[transaction.ip_address] += 1
            if transaction.is_fraud:
                ip_fraud[transaction.ip_address] += 1

    # ---------- Pre-compute per-customer velocity & amount stats ----------
    # Group transactions by customer, ordered by created_at (already sorted)
    from datetime import timedelta
    cust_txns: defaultdict[str, list] = defaultdict(list)
    for transaction, _ in rows:
        cust_txns[transaction.customer_id].append(transaction)

    # Per-customer historical amounts (for z-score)
    cust_amounts: defaultdict[str, list] = defaultdict(list)
    for transaction, _ in rows:
        if transaction.amount is not None:
            cust_amounts[transaction.customer_id].append((transaction.created_at, transaction.amount))

    # Pre-compute per-device transaction lists for velocity
    device_txns: defaultdict[str, list] = defaultdict(list)
    for transaction, _ in rows:
        if transaction.device_id:
            device_txns[transaction.device_id].append(transaction)

    def compute_velocity(transaction, window_hours: int) -> int:
        """Count txns by same customer OR device in the window before this txn."""
        t0 = transaction.created_at
        cutoff = t0 - timedelta(hours=window_hours) if t0 else None
        if cutoff is None:
            return 0
        count = 0
        # Customer velocity
        for t in cust_txns[transaction.customer_id]:
            if t.id != transaction.id and t.created_at and cutoff <= t.created_at < t0:
                count += 1
        # Device velocity (additional — some may overlap)
        if transaction.device_id:
            seen = {t.id for t in cust_txns[transaction.customer_id]}
            for t in device_txns[transaction.device_id]:
                if t.id != transaction.id and t.id not in seen and t.created_at and cutoff <= t.created_at < t0:
                    count += 1
        return count

    def compute_amount_zscore(transaction) -> float:
        history = [amt for (ts, amt) in cust_amounts[transaction.customer_id]
                   if ts and ts < transaction.created_at]
        if len(history) < 5:
            return 0.0
        deviation = pstdev(history)
        if deviation == 0:
            return 0.0
        return min(abs((transaction.amount - mean(history)) / deviation), 10.0)

    # ---------- Build feature matrix ----------
    feature_rows: list[list[float]] = []
    labels: list[int] = []
    for transaction, customer in rows:
        ip_rate = 0.0
        if transaction.ip_address and ip_totals[transaction.ip_address]:
            ip_rate = ip_fraud[transaction.ip_address] / ip_totals[transaction.ip_address]

        vel_1h = compute_velocity(transaction, 1)
        vel_24h = compute_velocity(transaction, 24)
        amount_zscore = compute_amount_zscore(transaction)
        is_new_device = float(bool(
            transaction.device_id
            and customer.primary_device_id
            and transaction.device_id != customer.primary_device_id
        ))
        geo_mismatch = float(transaction.geo_ip_match is False)

        values = {
            "amount_log": log1p(max(transaction.amount or 0, 0)),
            "hour": float(transaction.created_at.hour if transaction.created_at else 0),
            "account_age_days": float(customer.account_age_days or 0),
            "txn_velocity_1h": float(vel_1h),
            "txn_velocity_24h": float(vel_24h),
            "is_new_device": is_new_device,
            "amount_zscore": amount_zscore,
            "ip_fraud_rate": ip_rate,
            "geo_mismatch": geo_mismatch,
        }
        feature_rows.append([values[name] for name in MODEL_FEATURE_ORDER])
        labels.append(int(bool(transaction.is_fraud)))

    if len(set(labels)) < 2:
        raise ValueError("Training data must contain both legitimate and fraudulent transactions")

    x_train, x_test, y_train, y_test = train_test_split(
        feature_rows,
        labels,
        test_size=model_config.test_size,
        random_state=42,
        stratify=labels,
    )
    classifier = lgb.LGBMClassifier(
        num_leaves=model_config.lgbm_num_leaves,
        learning_rate=model_config.lgbm_learning_rate,
        n_estimators=model_config.lgbm_n_estimators,
        min_child_samples=model_config.lgbm_min_child_samples,
        class_weight="balanced",
        random_state=42,
        verbosity=-1,
    )
    classifier.fit(x_train, y_train, feature_name=list(MODEL_FEATURE_ORDER))
    probabilities = classifier.predict_proba(x_test)[:, 1]
    # Use 0.5 as the decision threshold for training evaluation
    predictions = (probabilities >= 0.5).astype(int)

    target_path = model_path or MODELS_DIR / "l1_lightgbm.txt"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    classifier.booster_.save_model(str(target_path))

    return {
        "model_path": str(target_path),
        "training_rows": len(x_train),
        "test_rows": len(x_test),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
        "auc_roc": round(float(roc_auc_score(y_test, probabilities)), 4),
        "feature_order": list(MODEL_FEATURE_ORDER),
    }

