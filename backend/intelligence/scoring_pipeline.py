"""Orchestration for the Phase 2 dual-engine scoring path."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from config import model_config
from database.models import Customer, RiskScore, Transaction

from .causal_engine import CausalExplanationEngine
from .chargeback_predictor import ChargebackPredictor
from .l1_engine import L1RiskEngine, L1Score
from .l2_graph_engine import GraphRiskEngine, L2Score


@dataclass
class ScoringResult:
    transaction_id: str
    aegis_score: float
    risk_level: str
    recommended_action: str
    l1: L1Score
    l2: Optional[L2Score]
    causal_explanation: dict[str, Any]
    counterfactual: str
    chargeback_probability: float
    predicted_dispute_days: int


class AegisScoringPipeline:
    """Apply L1 first, escalate riskier transactions to L2, and retain results."""

    def __init__(self, db: Session):
        self.db = db
        self.l1_engine = L1RiskEngine(db)
        self.l2_engine = GraphRiskEngine(db)
        self.causal_engine = CausalExplanationEngine()
        self.chargeback_predictor = ChargebackPredictor()

    def score(self, transaction: Transaction) -> ScoringResult:
        customer = self.db.get(Customer, transaction.customer_id) if transaction.customer_id else None
        l1 = self.l1_engine.score(transaction, customer)
        l2 = None
        final_score = l1.combined_score

        if l1.combined_score >= model_config.l1_fast_threshold:
            l2 = self.l2_engine.score(transaction)
            blended = 0.58 * l1.combined_score + 0.42 * l2.score
            # Never let L2 pull a high-confidence L1 signal below the detection line.
            # If L1 is already above high_risk_threshold, cap the blend upward.
            final_score = min(1.0, max(l1.combined_score, blended) if l1.combined_score >= model_config.high_risk_threshold else blended)

        risk_level, recommended_action = self._decision(final_score)
        causal_explanation, counterfactual = self.causal_engine.explain(
            transaction, customer, l1, l2, final_score
        )
        chargeback = self.chargeback_predictor.predict(transaction, customer, final_score)
        result = ScoringResult(
            transaction_id=transaction.id,
            aegis_score=round(final_score, 4),
            risk_level=risk_level,
            recommended_action=recommended_action,
            l1=l1,
            l2=l2,
            causal_explanation=causal_explanation,
            counterfactual=counterfactual,
            chargeback_probability=chargeback.probability,
            predicted_dispute_days=chargeback.predicted_days,
        )
        self._persist_if_known_transaction(transaction, result)
        return result

    def _persist_if_known_transaction(self, transaction: Transaction, result: ScoringResult) -> None:
        """Keep previews stateless but retain scores for stored Phase 1 records."""
        if self.db.get(Transaction, transaction.id) is None:
            return
        l2 = result.l2
        record = RiskScore(
            transaction_id=transaction.id,
            l1_rule_score=result.l1.rule_score,
            l1_rule_triggers=json.dumps(result.l1.triggers),
            l1_lgbm_score=result.l1.model_score,
            l1_lgbm_top_features=json.dumps(result.l1.top_features),
            l1_combined_score=result.l1.combined_score,
            l1_latency_ms=result.l1.latency_ms,
            l2_gnn_score=l2.score if l2 else None,
            l2_gnn_attention_weights=json.dumps(l2.attention_weights) if l2 else None,
            l2_ring_detected=l2.ring_detected if l2 else False,
            l2_ring_id=l2.ring_id if l2 else None,
            l2_ring_score=l2.ring_score if l2 else None,
            l2_latency_ms=l2.latency_ms if l2 else None,
            aegis_score=result.aegis_score,
            risk_level=result.risk_level,
            recommended_action=result.recommended_action,
            causal_explanation=json.dumps(result.causal_explanation),
            causal_top_factors=json.dumps(result.causal_explanation["top_factors"]),
            counterfactual=result.counterfactual,
            chargeback_probability=result.chargeback_probability,
            predicted_dispute_days=result.predicted_dispute_days,
        )
        self.db.add(record)
        self.db.commit()

    @staticmethod
    def _decision(score: float) -> tuple[str, str]:
        if score >= 0.90:
            return "critical", "block"
        if score >= model_config.high_risk_threshold:   # >= 0.60
            return "high", "block"
        if score >= model_config.l1_fast_threshold:     # >= 0.35
            return "medium", "step_up_auth"
        if score >= model_config.low_risk_threshold:    # >= 0.20
            return "medium", "review"
        return "low", "approve"
