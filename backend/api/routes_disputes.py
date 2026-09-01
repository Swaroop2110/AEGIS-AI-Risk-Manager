"""AEGIS Disputes API — Dispute defense and representment endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Dispute, Transaction
from defense.pipeline import DisputeDefensePipeline

router = APIRouter()


class DisputeDefenseRequest(BaseModel):
    """Request to auto-defend a dispute."""
    dispute_id: str
    transaction_id: str
    reason_code: str
    card_network: str
    amount: int


class DisputeDefenseResponse(BaseModel):
    """Auto-defense result."""
    dispute_id: str
    win_probability: float
    recommended_action: str
    evidence_completeness: float
    defense_strategy: dict
    evidence_pdf_url: Optional[str] = None
    cost_benefit: dict


@router.post("/auto-defend", response_model=DisputeDefenseResponse)
async def auto_defend_dispute(request: DisputeDefenseRequest, db: Session = Depends(get_db)):
    """Auto-generate dispute defense using the 4-agent pipeline."""
    transaction = db.get(Transaction, request.transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found. Generate or store it before filing a dispute.")
    dispute = db.get(Dispute, request.dispute_id)
    if dispute is None:
        dispute = Dispute(
            id=request.dispute_id,
            transaction_id=transaction.id,
            amount=request.amount,
            currency=transaction.currency,
            reason_code=request.reason_code,
            card_network=request.card_network,
            phase="chargeback",
            status="open",
        )
        db.add(dispute)
    else:
        dispute.amount = request.amount
        dispute.reason_code = request.reason_code
        dispute.card_network = request.card_network
    transaction.status = "disputed"
    db.commit()

    try:
        result = DisputeDefensePipeline(db).run(dispute, transaction)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return DisputeDefenseResponse(
        dispute_id=result.dispute_id,
        win_probability=result.win_probability,
        recommended_action=result.recommended_action,
        evidence_completeness=result.evidence_completeness,
        defense_strategy=result.defense_strategy,
        evidence_pdf_url=result.evidence_pdf_url,
        cost_benefit=result.cost_benefit,
    )


@router.get("/list")
async def list_disputes(db: Session = Depends(get_db)):
    """List all active disputes."""
    disputes = db.query(Dispute).order_by(Dispute.created_at.desc()).all()
    return {"disputes": [
        {
            "id": dispute.id,
            "transaction_id": dispute.transaction_id,
            "amount": dispute.amount,
            "reason_code": dispute.reason_code,
            "card_network": dispute.card_network,
            "status": dispute.status,
            "win_probability": dispute.win_probability,
            "recommended_action": dispute.recommended_action,
            "evidence_completeness": dispute.evidence_completeness,
            "evidence_pdf_url": f"/evidence/{dispute.evidence_pdf_path.rsplit('/', 1)[-1]}" if dispute.evidence_pdf_path else None,
        }
        for dispute in disputes
    ]}


@router.get("/{dispute_id}")
async def get_dispute(dispute_id: str, db: Session = Depends(get_db)):
    """Get detailed dispute information."""
    dispute = db.get(Dispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")
    try:
        strategy = json.loads(dispute.defense_strategy) if dispute.defense_strategy else {}
    except json.JSONDecodeError:
        strategy = {}
    return {
        "id": dispute.id,
        "transaction_id": dispute.transaction_id,
        "amount": dispute.amount,
        "currency": dispute.currency,
        "reason_code": dispute.reason_code,
        "card_network": dispute.card_network,
        "phase": dispute.phase,
        "status": dispute.status,
        "win_probability": dispute.win_probability,
        "recommended_action": dispute.recommended_action,
        "evidence_completeness": dispute.evidence_completeness,
        "defense_strategy": strategy,
        "evidence_pdf_url": f"/evidence/{dispute.evidence_pdf_path.rsplit('/', 1)[-1]}" if dispute.evidence_pdf_path else None,
    }
