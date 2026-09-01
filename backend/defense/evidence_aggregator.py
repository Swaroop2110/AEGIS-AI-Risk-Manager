"""Agent 1: retrieve and normalize evidence for a transaction dispute."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from sqlalchemy.orm import Session

from database.models import Customer, Evidence, Merchant, Transaction
from data_engine.evidence_generator import generate_evidence_for_transaction


@dataclass
class EvidenceBundle:
    transaction: Transaction
    customer: Customer | None
    merchant: Merchant | None
    sections: dict[str, Any]
    available_evidence: set[str]
    completeness: float


class EvidenceAggregator:
    """Collect auth-time, behavioural, and fulfilment evidence from the vault."""

    def __init__(self, db: Session):
        self.db = db

    def aggregate(self, transaction: Transaction) -> EvidenceBundle:
        evidence = self.db.query(Evidence).filter(Evidence.transaction_id == transaction.id).first()
        if evidence is None:
            evidence = generate_evidence_for_transaction(transaction)
            self.db.add(evidence)
            self.db.commit()

        customer = self.db.get(Customer, transaction.customer_id)
        merchant = self.db.get(Merchant, transaction.merchant_id)
        delivery = self._decode(evidence.delivery_proof)
        sections = {
            "authentication": {
                "method": evidence.auth_method,
                "otp_verified": evidence.otp_verified,
                "three_ds_version": evidence.three_ds_version,
                "eci_value": evidence.eci_value,
                "cavv_present": bool(evidence.cavv),
                "authorization_code": transaction.auth_code,
                "rrn": transaction.rrn,
            },
            "device_network": {
                "fingerprint": self._decode(evidence.device_fingerprint),
                "known_device": evidence.is_known_device,
                "device_trust_score": evidence.device_trust_score,
                "ip_address": transaction.ip_address,
                "ip_city": transaction.ip_city,
                "ip_reputation_score": evidence.ip_reputation_score,
                "proxy_or_vpn": evidence.ip_proxy_vpn,
            },
            "behaviour": self._decode(evidence.session_data),
            "delivery": delivery,
            "customer_history": {
                "customer_id": transaction.customer_id,
                "lifetime_value": evidence.customer_lifetime_value,
                "total_orders": evidence.customer_total_orders,
                "dispute_rate": evidence.customer_dispute_rate,
                "days_since_last_order": evidence.customer_days_since_last_order,
            },
            "transaction": {
                "transaction_id": transaction.id,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "payment_method": transaction.payment_method,
                "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
                "merchant": merchant.name if merchant else transaction.merchant_id,
            },
        }
        available = set()
        if evidence.otp_verified or evidence.eci_value or evidence.cavv:
            available.add("authentication")
        if evidence.device_fingerprint:
            available.add("device")
        if transaction.ip_address or evidence.ip_reputation_score is not None:
            available.add("network")
        if delivery:
            available.add("delivery")
        if evidence.customer_total_orders is not None:
            available.add("customer_history")
        if transaction.rrn or transaction.vpa:
            available.add("payment_trace")
        completeness = round(len(available) / 6, 3)
        return EvidenceBundle(transaction, customer, merchant, sections, available, completeness)

    @staticmethod
    def _decode(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
