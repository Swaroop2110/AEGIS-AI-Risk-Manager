"""AEGIS Dashboard API — Real-time data feeds for the Fraud War Room dashboard."""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
import json
import asyncio

from database.connection import get_db
from database.models import (
    Transaction, Dispute, RiskScore, Customer, Merchant, AttackSimulation
)

router = APIRouter()

# Connected WebSocket clients
connected_clients: List[WebSocket] = []


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get real-time dashboard statistics from the database."""
    total_txns = db.query(func.count(Transaction.id)).scalar() or 0
    fraud_detected = db.query(func.count(Transaction.id)).filter(Transaction.is_fraud == True).scalar() or 0
    fraud_rate = round(fraud_detected / total_txns, 4) if total_txns > 0 else 0.0

    # Dispute stats
    disputes_active = db.query(func.count(Dispute.id)).filter(
        Dispute.status.in_(["open", "under_review", "action_required"])
    ).scalar() or 0
    disputes_won = db.query(func.count(Dispute.id)).filter(Dispute.status == "won").scalar() or 0
    disputes_lost = db.query(func.count(Dispute.id)).filter(Dispute.status == "lost").scalar() or 0
    total_closed = disputes_won + disputes_lost
    win_rate = round(disputes_won / total_closed, 4) if total_closed > 0 else 0.0

    # Money saved: sum of fraud transaction amounts we scored as high risk
    saved_subq = (
        db.query(func.sum(Transaction.amount))
        .join(RiskScore, RiskScore.transaction_id == Transaction.id)
        .filter(Transaction.is_fraud == True, RiskScore.aegis_score >= 0.7)
        .scalar()
    ) or 0

    # Model metrics from latest scores
    scored_count = db.query(func.count(RiskScore.id)).scalar() or 0
    avg_latency = db.query(
        func.avg(RiskScore.l1_latency_ms + func.coalesce(RiskScore.l2_latency_ms, 0))
    ).scalar() or 0.0

    # Quick precision/recall from stored scores vs ground truth (sample)
    tp = fp = tn = fn = 0
    rows = (
        db.query(Transaction.is_fraud, RiskScore.aegis_score)
        .join(RiskScore, RiskScore.transaction_id == Transaction.id)
        .limit(5000)
        .all()
    )
    for actual_fraud, score in rows:
        predicted = (score or 0) >= 0.7
        if predicted and actual_fraud:
            tp += 1
        elif predicted:
            fp += 1
        elif actual_fraud:
            fn += 1
        else:
            tn += 1

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    return {
        "total_transactions": total_txns,
        "fraud_detected": fraud_detected,
        "fraud_rate": fraud_rate,
        "disputes_active": disputes_active,
        "disputes_won": disputes_won,
        "disputes_lost": disputes_lost,
        "win_rate": win_rate,
        "money_saved": int(saved_subq),
        "avg_score_latency_ms": round(float(avg_latency), 2),
        "scored_transactions": scored_count,
        "model_precision": precision,
        "model_recall": recall,
        "model_f1": f1,
    }


@router.get("/transactions/recent")
async def get_recent_transactions(limit: int = 50, db: Session = Depends(get_db)):
    """Get most recent transactions with risk scores."""
    rows = (
        db.query(Transaction, RiskScore)
        .outerjoin(
            RiskScore,
            (RiskScore.transaction_id == Transaction.id)
        )
        .order_by(desc(Transaction.created_at))
        .limit(limit)
        .all()
    )
    result = []
    for txn, score in rows:
        result.append({
            "id": txn.id,
            "customer_id": txn.customer_id,
            "merchant_id": txn.merchant_id,
            "amount": txn.amount,
            "currency": txn.currency,
            "payment_method": txn.payment_method,
            "status": txn.status,
            "is_fraud": txn.is_fraud,
            "fraud_type": txn.fraud_type,
            "created_at": txn.created_at.isoformat() if txn.created_at else None,
            "aegis_score": score.aegis_score if score else None,
            "risk_level": score.risk_level if score else None,
            "recommended_action": score.recommended_action if score else None,
            "ring_detected": score.l2_ring_detected if score else False,
            "ring_id": score.l2_ring_id if score else None,
        })
    return {"transactions": result}


@router.get("/graph/rings")
async def get_fraud_rings(db: Session = Depends(get_db)):
    """Get detected fraud ring data for graph visualization."""
    # Find all ring IDs from risk scores
    ring_rows = (
        db.query(RiskScore.l2_ring_id, func.count(RiskScore.id).label("tx_count"))
        .filter(RiskScore.l2_ring_detected == True, RiskScore.l2_ring_id.isnot(None))
        .group_by(RiskScore.l2_ring_id)
        .order_by(desc("tx_count"))
        .limit(20)
        .all()
    )

    rings = []
    for ring_id, tx_count in ring_rows:
        # Get transactions in this ring
        ring_txns = (
            db.query(Transaction)
            .join(RiskScore, RiskScore.transaction_id == Transaction.id)
            .filter(RiskScore.l2_ring_id == ring_id)
            .all()
        )
        total_amount = sum(t.amount for t in ring_txns)
        unique_customers = len(set(t.customer_id for t in ring_txns))
        unique_devices = len(set(t.device_id for t in ring_txns if t.device_id))
        unique_ips = len(set(t.ip_address for t in ring_txns if t.ip_address))

        rings.append({
            "ring_id": ring_id,
            "transaction_count": tx_count,
            "total_amount": total_amount,
            "unique_customers": unique_customers,
            "unique_devices": unique_devices,
            "unique_ips": unique_ips,
            "transactions": [
                {
                    "id": t.id,
                    "amount": t.amount,
                    "customer_id": t.customer_id,
                    "device_id": t.device_id,
                    "ip_address": t.ip_address,
                    "payment_method": t.payment_method,
                    "fraud_type": t.fraud_type,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in ring_txns[:50]
            ],
        })
    return {"rings": rings, "total_rings": len(rings)}


@router.get("/graph/nodes/{entity_id}")
async def get_entity_subgraph(entity_id: str, hops: int = 2, db: Session = Depends(get_db)):
    """Get a k-hop subgraph around an entity for the graph explorer."""
    from database.models import GraphEdge

    # Find direct edges involving this entity
    edges_out = (
        db.query(GraphEdge)
        .filter(GraphEdge.source_id == entity_id)
        .limit(200)
        .all()
    )
    edges_in = (
        db.query(GraphEdge)
        .filter(GraphEdge.target_id == entity_id)
        .limit(200)
        .all()
    )

    nodes = {}
    links = []

    def add_node(node_id: str, node_type: str):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": node_type}

    for edge in edges_out + edges_in:
        add_node(edge.source_id, edge.source_type)
        add_node(edge.target_id, edge.target_type)
        links.append({
            "source": edge.source_id,
            "target": edge.target_id,
            "type": edge.edge_type,
            "amount": edge.amount,
        })

    return {"nodes": list(nodes.values()), "links": links}


@router.get("/metrics/model")
async def get_model_metrics(db: Session = Depends(get_db)):
    """Get ML model performance metrics from stored evaluation data."""
    from intelligence.evaluation import evaluate_stored_scores
    return evaluate_stored_scores(db)


@router.get("/attacks/recent")
async def get_recent_attacks(limit: int = 10, db: Session = Depends(get_db)):
    """Get recent attack simulation results."""
    attacks = (
        db.query(AttackSimulation)
        .order_by(desc(AttackSimulation.created_at))
        .limit(limit)
        .all()
    )
    return {"attacks": [
        {
            "attack_id": a.id,
            "attack_type": a.attack_type,
            "intensity": a.intensity,
            "transactions_injected": a.transactions_injected,
            "detected_count": a.detected_count,
            "detection_rate": a.detection_rate,
            "avg_detection_latency_ms": a.avg_detection_latency_ms,
            "rings_identified": a.rings_identified,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in attacks
    ]}


@router.get("/disputes/analytics")
async def get_dispute_analytics(db: Session = Depends(get_db)):
    """Get dispute analytics — reason code breakdown, win rate trends."""
    reason_rows = (
        db.query(Dispute.reason_code, func.count(Dispute.id).label("count"))
        .group_by(Dispute.reason_code)
        .order_by(desc("count"))
        .all()
    )
    status_rows = (
        db.query(Dispute.status, func.count(Dispute.id).label("count"))
        .group_by(Dispute.status)
        .all()
    )
    # Win probability distribution from stored data
    wp_rows = (
        db.query(Dispute.win_probability)
        .filter(Dispute.win_probability.isnot(None))
        .all()
    )
    wp_values = [row[0] for row in wp_rows if row[0] is not None]
    avg_win_prob = round(sum(wp_values) / len(wp_values), 4) if wp_values else 0.0

    return {
        "reason_code_breakdown": [{"code": code, "count": cnt} for code, cnt in reason_rows],
        "status_breakdown": [{"status": status, "count": cnt} for status, cnt in status_rows],
        "avg_win_probability": avg_win_prob,
        "total_disputes": sum(cnt for _, cnt in status_rows),
    }


@router.websocket("/ws/stream")
async def transaction_stream(websocket: WebSocket):
    """WebSocket for real-time transaction streaming to the dashboard."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Heartbeat every 5 seconds
            await asyncio.sleep(5)
            await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


async def broadcast_transaction(transaction_data: dict):
    """Broadcast a scored transaction to all connected dashboard clients."""
    message = json.dumps({"type": "transaction", "data": transaction_data})
    dead = []
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            dead.append(client)
    for client in dead:
        if client in connected_clients:
            connected_clients.remove(client)
