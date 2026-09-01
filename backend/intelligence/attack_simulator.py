"""Phase 4 chaos-engineering attacks that exercise the real scoring pipeline."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from config import data_config, model_config
from data_engine.evidence_generator import generate_evidence_bulk
from data_engine.fraud_injector import inject_fraud
from data_engine.graph_builder import persist_transaction_graph
from database.models import AttackSimulation, Customer, Merchant, Transaction

from .scoring_pipeline import AegisScoringPipeline


ATTACK_VECTORS = {
    "velocity": "velocity",
    "mule_ring": "mule",
    "friendly_fraud": "friendly",
    "device_spoofing": "spoofing",
    "account_takeover": "ato",
}


class AttackSimulator:
    """Inject a configured fraud vector, score it, and retain the demo result."""

    def __init__(self, db: Session):
        self.db = db

    def launch(self, attack_type: str, intensity: str, num_transactions: int) -> dict[str, Any]:
        vector = ATTACK_VECTORS.get(attack_type)
        if vector is None:
            raise ValueError(f"Unsupported attack_type. Choose one of: {', '.join(ATTACK_VECTORS)}")
        if intensity not in {"low", "medium", "high"}:
            raise ValueError("intensity must be low, medium, or high")
        if num_transactions < 1:
            raise ValueError("num_transactions must be at least 1")

        seed_transaction = self.db.query(Transaction).order_by(Transaction.created_at.desc()).first()
        customers = self.db.query(Customer).all()
        merchants = self.db.query(Merchant).all()
        if seed_transaction is None or not customers or not merchants:
            raise ValueError("Generate Phase 1 data before launching an attack simulation")

        weights = {name: 0.0 for name in {"velocity", "mule", "friendly", "spoofing", "ato"}}
        weights[vector] = 1.0
        attack_config = replace(
            data_config,
            seed=data_config.seed + len(customers) + num_transactions,
            velocity_attack_pct=weights["velocity"],
            mule_ring_pct=weights["mule"],
            friendly_fraud_pct=weights["friendly"],
            device_spoofing_pct=weights["spoofing"],
            account_takeover_pct=weights["ato"],
        )
        injected = inject_fraud(
            [seed_transaction],
            customers,
            merchants,
            config=attack_config,
            target_fraud_count=num_transactions,
        )
        transactions = injected["injected_transactions"]
        self.db.bulk_save_objects(transactions)
        if injected["disputes"]:
            self.db.bulk_save_objects(injected["disputes"])
        self.db.commit()

        evidence = generate_evidence_bulk(transactions)
        self.db.bulk_save_objects(evidence)
        self.db.commit()
        persist_transaction_graph(self.db, transactions)

        scored = []
        pipeline = AegisScoringPipeline(self.db)
        for transaction in transactions:
            stored = self.db.get(Transaction, transaction.id)
            scored.append(pipeline.score(stored))

        detected = [
            result for result in scored
            if result.aegis_score >= model_config.high_risk_threshold or (result.l2 and result.l2.ring_detected)
        ]
        latencies = [result.l1.latency_ms + (result.l2.latency_ms if result.l2 else 0) for result in scored]
        rings = {result.l2.ring_id for result in scored if result.l2 and result.l2.ring_id}
        attack_id = f"atk_{uuid.uuid4().hex[:16]}"
        summary = {
            "scores": [
                {
                    "transaction_id": result.transaction_id,
                    "aegis_score": result.aegis_score,
                    "risk_level": result.risk_level,
                    "ring_id": result.l2.ring_id if result.l2 else None,
                }
                for result in scored
            ],
            "created_at": datetime.utcnow().isoformat(),
        }
        simulation = AttackSimulation(
            id=attack_id,
            attack_type=attack_type,
            intensity=intensity,
            transactions_injected=len(transactions),
            detected_count=len(detected),
            detection_rate=len(detected) / len(transactions),
            avg_detection_latency_ms=sum(latencies) / len(latencies),
            rings_identified=len(rings),
            result_summary=json.dumps(summary),
        )
        self.db.add(simulation)
        self.db.commit()
        return {
            "attack_id": attack_id,
            "attack_type": attack_type,
            "transactions_injected": len(transactions),
            "detected_count": len(detected),
            "detection_rate": round(len(detected) / len(transactions), 4),
            "avg_detection_latency_ms": round(sum(latencies) / len(latencies), 3),
            "rings_identified": len(rings),
            "message": f"{attack_type} attack injected and evaluated through the live AEGIS pipeline",
        }
