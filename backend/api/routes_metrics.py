"""AEGIS Metrics API — Model evaluation, ablation study, and ROI analytics."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db

router = APIRouter()


@router.get("/evaluate")
async def evaluate_model(threshold: float = 0.7, db: Session = Depends(get_db)):
    """Run full precision/recall/F1/cost evaluation on all stored scores."""
    from intelligence.evaluation import evaluate_stored_scores
    return evaluate_stored_scores(db, threshold=threshold)


@router.get("/ablation")
async def ablation_study(db: Session = Depends(get_db)):
    """Compare performance of each AEGIS layer in isolation."""
    from sqlalchemy import func
    from database.models import Transaction, RiskScore

    rows = (
        db.query(Transaction.is_fraud, RiskScore.l1_rule_score,
                 RiskScore.l1_lgbm_score, RiskScore.l1_combined_score,
                 RiskScore.l2_gnn_score, RiskScore.aegis_score)
        .join(RiskScore, RiskScore.transaction_id == Transaction.id)
        .limit(10000)
        .all()
    )
    if not rows:
        return {"message": "No scored transactions found. Generate and score data first."}

    def compute_metrics(predictions, actuals, threshold=0.5):
        tp = fp = tn = fn = 0
        for pred, actual in zip(predictions, actuals):
            p = (pred or 0) >= threshold
            a = bool(actual)
            if p and a:
                tp += 1
            elif p:
                fp += 1
            elif a:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "false_positive_rate": round(fpr, 4),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        }

    actuals = [r[0] for r in rows]
    layers = {
        "L1 Rules Only": [r[1] for r in rows],
        "L1 LightGBM Only": [r[2] for r in rows],
        "L1 Combined": [r[3] for r in rows],
        "L2 Graph Only": [r[4] for r in rows],
        "AEGIS Full": [r[5] for r in rows],
    }

    ablation = {}
    for name, preds in layers.items():
        valid = [(p, a) for p, a in zip(preds, actuals) if p is not None]
        if valid:
            p_list, a_list = zip(*valid)
            ablation[name] = compute_metrics(p_list, a_list)
        else:
            ablation[name] = {"note": "No scores available for this layer yet"}

    return {
        "ablation": ablation,
        "total_rows": len(rows),
        "note": "Threshold = 0.5 for all layers. Train the L1 model (POST /api/v1/scoring/train) to improve LightGBM scores.",
    }


@router.get("/roi")
async def roi_calculator(db: Session = Depends(get_db)):
    """Calculate estimated ROI from AEGIS deployment."""
    from database.models import Transaction, RiskScore, Dispute
    from sqlalchemy import func

    total_txns = db.query(func.count(Transaction.id)).scalar() or 0
    total_amount = db.query(func.sum(Transaction.amount)).scalar() or 0
    fraud_txns = db.query(func.count(Transaction.id)).filter(Transaction.is_fraud == True).scalar() or 0
    fraud_amount = db.query(func.sum(Transaction.amount)).filter(Transaction.is_fraud == True).scalar() or 0

    # Chargebacks prevented = fraud we scored as high risk
    prevented = (
        db.query(func.count(Transaction.id))
        .join(RiskScore, RiskScore.transaction_id == Transaction.id)
        .filter(Transaction.is_fraud == True, RiskScore.aegis_score >= 0.7)
        .scalar()
    ) or 0
    prevented_amount = (
        db.query(func.sum(Transaction.amount))
        .join(RiskScore, RiskScore.transaction_id == Transaction.id)
        .filter(Transaction.is_fraud == True, RiskScore.aegis_score >= 0.7)
        .scalar()
    ) or 0

    # Disputes auto-defended
    disputes_total = db.query(func.count(Dispute.id)).scalar() or 0
    disputes_defended = db.query(func.count(Dispute.id)).filter(
        Dispute.recommended_action.in_(["auto_defend", "review"])
    ).scalar() or 0

    # Chargeback cost multiplier = 2.5x
    MULTIPLIER = 2.5
    ARBITRATION_FEE = 40_000  # INR paise

    fraud_loss_without_aegis = int((fraud_amount or 0) * MULTIPLIER)
    fraud_loss_with_aegis = int(((fraud_amount or 0) - (prevented_amount or 0)) * MULTIPLIER)
    money_saved = fraud_loss_without_aegis - fraud_loss_with_aegis

    return {
        "summary": {
            "total_transactions": total_txns,
            "total_amount_paise": int(total_amount or 0),
            "fraud_transactions": fraud_txns,
            "fraud_amount_paise": int(fraud_amount or 0),
        },
        "prevention": {
            "chargebacks_prevented": prevented,
            "amount_prevented_paise": int(prevented_amount or 0),
            "fraud_loss_without_aegis_paise": fraud_loss_without_aegis,
            "fraud_loss_with_aegis_paise": fraud_loss_with_aegis,
            "money_saved_paise": money_saved,
        },
        "dispute_defense": {
            "total_disputes": disputes_total,
            "disputes_auto_defended": disputes_defended,
            "defense_rate": round(disputes_defended / disputes_total, 4) if disputes_total > 0 else 0.0,
            "arbitration_fees_saved_paise": disputes_defended * ARBITRATION_FEE,
        },
        "roi_summary": {
            "total_value_protected_paise": money_saved + disputes_defended * ARBITRATION_FEE,
            "note": "Amounts in paise (INR × 100). Divide by 100 for INR.",
        },
    }
