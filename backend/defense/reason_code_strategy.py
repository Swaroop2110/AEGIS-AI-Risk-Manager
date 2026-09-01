"""Scheme-specific representment strategy selection."""

from __future__ import annotations

from typing import Any


STRATEGIES = {
    ("visa", "10.4"): {
        "attack_type": "card_absent_fraud",
        "primary": "3DS ECI=05 and authentication proof",
        "evidence": ["3DS/OTP logs", "device fingerprint match", "IP geolocation consistency", "prior trusted activity"],
    },
    ("visa", "13.1"): {
        "attack_type": "merchandise_not_received",
        "primary": "carrier confirmation with signed delivery proof",
        "evidence": ["tracking record", "delivery timestamp", "GPS coordinates", "recipient signature"],
    },
    ("mastercard", "4837"): {
        "attack_type": "no_authorization",
        "primary": "OTP token and established-device evidence",
        "evidence": ["OTP verification", "device fingerprint", "customer order history", "IP trace"],
    },
    ("mastercard", "4853"): {
        "attack_type": "not_as_described",
        "primary": "fulfilment and customer-agreement evidence",
        "evidence": ["delivery proof", "return-policy acceptance", "customer communication", "product evidence"],
    },
    ("rupay", "4522"): {
        "attack_type": "disputed_transaction",
        "primary": "RuPay OTP and fulfilment evidence",
        "evidence": ["OTP verification", "authorization timestamp", "RRN", "fulfilment proof"],
    },
    ("npci upi", "u01"): {
        "attack_type": "upi_dispute",
        "primary": "NPCI transaction trace and UPI authorization record",
        "evidence": ["UPI VPA", "RRN", "OTP/UPI authorization", "URCS clearing trace"],
    },
    ("npci upi", "u03"): {
        "attack_type": "upi_dispute",
        "primary": "NPCI transaction trace and UPI authorization record",
        "evidence": ["UPI VPA", "RRN", "OTP/UPI authorization", "URCS clearing trace"],
    },
}


def select_strategy(card_network: str | None, reason_code: str, available_evidence: set[str]) -> dict[str, Any]:
    """Select and rank the strongest available strategy for a scheme reason code."""
    scheme = (card_network or "").strip().lower()
    code = reason_code.strip().lower()
    base = STRATEGIES.get((scheme, code), {
        "attack_type": "general_dispute",
        "primary": "authentication, transaction context, and fulfilment evidence",
        "evidence": ["authentication proof", "device and IP context", "delivery evidence", "customer history"],
    })
    selected = [item for item in base["evidence"] if _is_available(item, available_evidence)]
    missing = [item for item in base["evidence"] if item not in selected]
    return {
        "scheme": card_network or "Unknown",
        "reason_code": reason_code,
        "attack_type": base["attack_type"],
        "primary": base["primary"],
        "selected_evidence": selected,
        "missing_evidence": missing,
    }


def _is_available(item: str, available: set[str]) -> bool:
    item = item.lower()
    if "3ds" in item or "otp" in item or "authorization" in item:
        return "authentication" in available
    if "device" in item:
        return "device" in available
    if "ip" in item or "geolocation" in item:
        return "network" in available
    if any(word in item for word in ("delivery", "tracking", "gps", "signature", "fulfilment")):
        return "delivery" in available
    if "history" in item or "communication" in item:
        return "customer_history" in available
    if "rrn" in item or "vpa" in item or "urcs" in item:
        return "payment_trace" in available
    return False
