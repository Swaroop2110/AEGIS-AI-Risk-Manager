"""Phase 3 multi-agent dispute representment orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from sqlalchemy.orm import Session

from database.models import Dispute, RiskScore, Transaction

from .evidence_aggregator import EvidenceAggregator
from .pdf_compiler import EvidencePDFCompiler
from .reason_code_strategy import select_strategy
from .win_predictor import DefenseDecision, WinProbabilityPredictor


@dataclass
class DefenseResult:
    dispute_id: str
    win_probability: float
    recommended_action: str
    evidence_completeness: float
    defense_strategy: dict[str, Any]
    evidence_pdf_url: str
    cost_benefit: dict[str, Any]


class DisputeDefensePipeline:
    """Run the Evidence → Strategy → Win → PDF agent sequence."""

    def __init__(self, db: Session):
        self.db = db
        self.aggregator = EvidenceAggregator(db)
        self.predictor = WinProbabilityPredictor()
        self.compiler = EvidencePDFCompiler()

    def run(self, dispute: Dispute, transaction: Transaction) -> DefenseResult:
        bundle = self.aggregator.aggregate(transaction)
        strategy = select_strategy(dispute.card_network, dispute.reason_code, bundle.available_evidence)
        decision = self.predictor.predict(bundle, strategy)
        latest_score = (
            self.db.query(RiskScore)
            .filter(RiskScore.transaction_id == transaction.id)
            .order_by(RiskScore.scored_at.desc(), RiskScore.id.desc())
            .first()
        )
        causal_explanation = self._decode(latest_score.causal_explanation) if latest_score else {}
        counterfactual = latest_score.counterfactual if latest_score else None
        path = self.compiler.compile(
            dispute.id,
            dispute.reason_code,
            bundle,
            strategy,
            decision,
            causal_explanation,
            counterfactual,
        )

        dispute.win_probability = decision.win_probability
        dispute.recommended_action = decision.recommended_action
        dispute.evidence_completeness = bundle.completeness
        dispute.defense_strategy = json.dumps(strategy)
        dispute.evidence_pdf_path = str(path)
        dispute.status = "under_review" if decision.recommended_action != "accept" else "action_required"
        self.db.commit()
        return DefenseResult(
            dispute_id=dispute.id,
            win_probability=decision.win_probability,
            recommended_action=decision.recommended_action,
            evidence_completeness=bundle.completeness,
            defense_strategy=strategy,
            evidence_pdf_url=f"/evidence/{path.name}",
            cost_benefit=decision.cost_benefit,
        )

    @staticmethod
    def _decode(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
