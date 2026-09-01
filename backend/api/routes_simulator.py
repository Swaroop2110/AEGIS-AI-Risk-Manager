"""AEGIS Attack Simulator API — Chaos engineering endpoints for live demo."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import AttackSimulation
from intelligence.attack_simulator import AttackSimulator

router = APIRouter()


class AttackRequest(BaseModel):
    """Request to simulate a fraud attack."""
    attack_type: str  # velocity, mule_ring, friendly_fraud, device_spoofing, account_takeover
    intensity: str = "medium"  # low, medium, high
    num_transactions: int = 10


class AttackResponse(BaseModel):
    """Attack simulation result."""
    attack_id: str
    attack_type: str
    transactions_injected: int
    detected_count: int
    detection_rate: float
    avg_detection_latency_ms: float
    rings_identified: int
    message: str


@router.post("/attack", response_model=AttackResponse)
async def launch_attack(request: AttackRequest, db: Session = Depends(get_db)):
    """Launch a simulated fraud attack for live demo."""
    try:
        result = AttackSimulator(db).launch(
            request.attack_type,
            request.intensity,
            request.num_transactions,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return AttackResponse(**result)


@router.get("/attacks")
async def list_attack_history(db: Session = Depends(get_db)):
    """List past attack simulations and their results."""
    attacks = db.query(AttackSimulation).order_by(AttackSimulation.created_at.desc()).all()
    return {"attacks": [
        {
            "attack_id": attack.id,
            "attack_type": attack.attack_type,
            "intensity": attack.intensity,
            "transactions_injected": attack.transactions_injected,
            "detected_count": attack.detected_count,
            "detection_rate": attack.detection_rate,
            "avg_detection_latency_ms": attack.avg_detection_latency_ms,
            "rings_identified": attack.rings_identified,
            "result_summary": json.loads(attack.result_summary) if attack.result_summary else {},
            "created_at": attack.created_at,
        }
        for attack in attacks
    ]}
