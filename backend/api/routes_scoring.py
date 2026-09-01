"""AEGIS Scoring API — Transaction risk scoring endpoints."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Transaction
from intelligence.scoring_pipeline import AegisScoringPipeline
from intelligence.training import train_l1_lightgbm

router = APIRouter()


class TransactionScoreRequest(BaseModel):
    """Request body for scoring a transaction.

    When ``transaction_id`` refers to an existing DB record, all other fields
    are optional — they are read from the stored transaction.
    """
    transaction_id: Optional[str] = None
    amount: Optional[int] = None        # in paise; required only for new transactions
    currency: str = "INR"
    payment_method: Optional[str] = None
    card_network: Optional[str] = None
    card_issuer: Optional[str] = None
    card_last4: Optional[str] = None
    vpa: Optional[str] = None
    customer_id: Optional[str] = None
    merchant_id: Optional[str] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    ip_city: Optional[str] = None
    auth_type: Optional[str] = None
    geo_ip_match: Optional[bool] = None


class ScoreResponse(BaseModel):
    """Risk scoring response."""
    transaction_id: str
    aegis_score: float
    risk_level: str
    recommended_action: str
    l1_score: float
    l2_score: Optional[float] = None
    l1_latency_ms: float
    l2_latency_ms: Optional[float] = None
    causal_explanation: Optional[dict] = None
    counterfactual: Optional[str] = None
    chargeback_probability: Optional[float] = None
    ring_detected: bool = False
    ring_id: Optional[str] = None


def _build_response(result) -> ScoreResponse:
    return ScoreResponse(
        transaction_id=result.transaction_id,
        aegis_score=result.aegis_score,
        risk_level=result.risk_level,
        recommended_action=result.recommended_action,
        l1_score=result.l1.combined_score,
        l2_score=result.l2.score if result.l2 else None,
        l1_latency_ms=result.l1.latency_ms,
        l2_latency_ms=result.l2.latency_ms if result.l2 else None,
        causal_explanation=result.causal_explanation,
        counterfactual=result.counterfactual,
        chargeback_probability=result.chargeback_probability,
        ring_detected=result.l2.ring_detected if result.l2 else False,
        ring_id=result.l2.ring_id if result.l2 else None,
    )


@router.post("/score", response_model=ScoreResponse)
async def score_transaction(request: TransactionScoreRequest, db: Session = Depends(get_db)):
    """Score a transaction through the dual-engine pipeline (L1 fast + L2 deep).

    Pass only ``transaction_id`` to score an existing DB transaction.
    Pass all fields to score a new/preview transaction on the fly.
    """
    transaction = db.get(Transaction, request.transaction_id) if request.transaction_id else None
    if transaction is None:
        # Validate required fields for new transactions
        if not request.amount or not request.payment_method or not request.customer_id or not request.merchant_id:
            raise HTTPException(
                status_code=422,
                detail="When transaction_id is not in the database, amount, payment_method, customer_id, and merchant_id are required.",
            )
        transaction = Transaction(
            id=request.transaction_id or f"preview_{uuid.uuid4().hex[:24]}",
            customer_id=request.customer_id,
            merchant_id=request.merchant_id,
            amount=request.amount,
            currency=request.currency,
            payment_method=request.payment_method,
            card_network=request.card_network,
            card_issuer=request.card_issuer,
            card_last4=request.card_last4,
            vpa=request.vpa,
            device_id=request.device_id,
            ip_address=request.ip_address,
            ip_city=request.ip_city,
            auth_type=request.auth_type,
            geo_ip_match=request.geo_ip_match,
            status="captured",
            created_at=datetime.utcnow(),
        )

    result = AegisScoringPipeline(db).score(transaction)
    return _build_response(result)


@router.get("/score/{transaction_id}", response_model=ScoreResponse)
async def score_existing_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Score an existing DB transaction by ID. Convenient for the dashboard."""
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    result = AegisScoringPipeline(db).score(transaction)
    return _build_response(result)


@router.post("/score/batch")
async def score_batch(limit: int = 100, db: Session = Depends(get_db)):
    """Score a batch of unscored DB transactions. Use for bulk scoring after data generation."""
    from sqlalchemy import text
    from database.models import RiskScore

    # Find transactions without a score yet
    scored_ids = {row[0] for row in db.query(RiskScore.transaction_id).all()}
    txns = db.query(Transaction).filter(Transaction.id.notin_(scored_ids)).limit(limit).all()

    if not txns:
        return {"message": "All transactions are already scored.", "scored": 0}

    pipeline = AegisScoringPipeline(db)
    scored = 0
    errors = 0
    for txn in txns:
        try:
            pipeline.score(txn)
            scored += 1
        except Exception:
            errors += 1

    return {"scored": scored, "errors": errors, "total_unscored_processed": len(txns)}


@router.post("/train")
async def train_l1_model(db: Session = Depends(get_db)):
    """Train and save the optional LightGBM L1 model from generated labels."""
    try:
        return train_l1_lightgbm(db)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/batch/{batch_id}")
async def get_batch_scores(batch_id: str):
    """Get scoring results for a batch of transactions."""
    return {"batch_id": batch_id, "status": "pending", "message": "Batch scoring — Phase 2"}
