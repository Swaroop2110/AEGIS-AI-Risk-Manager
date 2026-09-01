import json
import base64
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import numpy as np

from database.models import Transaction, Evidence, FraudType

def generate_evidence_for_transaction(txn: Transaction) -> Evidence:
    """
    Generate the Evidence Vault entry for a transaction, containing auth-time signals.
    
    Args:
        txn (Transaction): The transaction to generate evidence for.
        
    Returns:
        Evidence: The generated evidence object.
    """
    is_fraud = txn.is_fraud
    fraud_type = txn.fraud_type
    
    # Base logic for signal generation
    # Fraud transactions generally look suspicious (except friendly fraud which mimics legitimate)
    looks_suspicious = is_fraud and fraud_type != FraudType.FRIENDLY_FRAUD

    # 1. Authentication Evidence
    auth_method = "unknown"
    if txn.payment_method in ["credit_card", "debit_card"]:
        auth_method = "3ds"
    elif txn.payment_method == "upi":
        auth_method = "otp"
    elif txn.payment_method == "wallet":
        auth_method = "pin"
        
    otp_verified = True if txn.status in ["captured", "authorized"] else False
    
    three_ds_version = None
    eci_value = None
    cavv = None
    
    if auth_method == "3ds":
        three_ds_version = "2.0" if random.random() < 0.7 else "1.0"
        
        if txn.status == "captured":
            eci_value = "05" if not looks_suspicious else random.choice(["05", "02"])
        else:
            eci_value = random.choice(["02", "07"])
            
        cavv = base64.b64encode(uuid.uuid4().bytes).decode('utf-8')[:28]
        
    # 2. Device Intelligence
    device_model = "iPhone 13" if random.random() < 0.5 else "Samsung Galaxy S22"
    device_os = "iOS 16" if "iPhone" in device_model else "Android 13"
    
    device_fingerprint = {
        "model": device_model,
        "os": device_os,
        "screen_res": "1170x2532" if "iPhone" in device_model else "1080x2340",
        "timezone": "Asia/Kolkata",
        "language": "en-IN"
    }
    
    if looks_suspicious:
        device_trust_score = random.uniform(0.1, 0.4)
        is_known_device = False
        device_age_days = random.randint(0, 2)
    else:
        device_trust_score = random.uniform(0.7, 1.0)
        is_known_device = random.random() < 0.9  # 90% chance it's a known device for legit txns
        device_age_days = random.randint(30, 365)
        
    # 3. Network Intelligence
    if looks_suspicious:
        ip_reputation_score = random.uniform(0.1, 0.5)
        ip_proxy_vpn = random.random() < 0.60  # 60% of fraud uses VPN
        ip_tor = random.random() < 0.01        # 1% of fraud uses Tor
        ip_datacenter = random.random() < 0.40 # 40% of fraud from datacenters
    else:
        ip_reputation_score = random.uniform(0.8, 1.0)
        ip_proxy_vpn = random.random() < 0.05  # 5% of legit uses VPN
        ip_tor = False
        ip_datacenter = random.random() < 0.03 # 3% of legit from datacenters

    # 4. Behavioral Signals
    if looks_suspicious and fraud_type in [FraudType.VELOCITY_ATTACK, FraudType.ACCOUNT_TAKEOVER]:
        checkout_time_sec = random.randint(1, 5)  # Bot-like speed
        time_on_page = checkout_time_sec
        typing_speed = random.randint(200, 300) # Unnaturally fast
        mouse_score = random.uniform(0.1, 0.3) # Robotic
    else:
        checkout_time_sec = random.randint(15, 180)
        time_on_page = checkout_time_sec + random.randint(10, 60)
        typing_speed = random.randint(40, 100)
        mouse_score = random.uniform(0.7, 1.0) # Natural
        
    session_data = {
        "time_on_page": time_on_page,
        "click_count": random.randint(3, 20),
        "scroll_depth": random.randint(30, 100),
        "mouse_movement_score": mouse_score,
        "typing_speed": typing_speed
    }
    
    is_first_purchase = (not is_known_device) and (random.random() < 0.5)

    # 5. Customer History Snapshot
    if is_fraud and fraud_type == FraudType.FRIENDLY_FRAUD:
        # Friendly fraud usually has a good history
        customer_lifetime_value = random.uniform(10000.0, 500000.0)
        customer_total_orders = random.randint(5, 50)
        customer_dispute_rate = random.uniform(0.01, 0.05)
        customer_days_since_last_order = random.randint(1, 30)
    elif looks_suspicious:
        # New or throwaway accounts
        customer_lifetime_value = random.uniform(0.0, 5000.0)
        customer_total_orders = random.randint(0, 3)
        customer_dispute_rate = random.uniform(0.0, 0.2) if customer_total_orders > 0 else 0.0
        customer_days_since_last_order = random.randint(0, 5) if customer_total_orders > 0 else 0
    else:
        # Normal customer
        customer_lifetime_value = random.uniform(2000.0, 200000.0)
        customer_total_orders = random.randint(1, 100)
        customer_dispute_rate = random.uniform(0.0, 0.01) if customer_total_orders > 0 else 0.0
        customer_days_since_last_order = random.randint(2, 60)

    # 6. Delivery Proof
    delivery_proof = None
    if txn.status in ["captured", "disputed"]:
        delivery_timestamp = (txn.created_at + timedelta(days=random.randint(1, 5))).isoformat() if txn.created_at else datetime.utcnow().isoformat()
        delivery_proof = {
            "carrier_name": random.choice(["Delhivery", "BlueDart", "Amazon Shipping", "Ecom Express"]),
            "tracking_url": f"https://tracking.example.com/{uuid.uuid4().hex[:10]}",
            "delivery_timestamp": delivery_timestamp,
            "gps_lat": round(txn.geo_lat or 19.076, 4) + random.uniform(-0.001, 0.001),
            "gps_lon": round(txn.geo_lon or 72.877, 4) + random.uniform(-0.001, 0.001),
            "signature_url": f"https://s3.example.com/sigs/{uuid.uuid4().hex}.png" if random.random() > 0.3 else None
        }

    # Compile the full evidence bundle
    compiled_evidence = {
        "auth": {
            "method": auth_method,
            "otp_verified": otp_verified,
            "eci": eci_value
        },
        "device": device_fingerprint,
        "network": {
            "reputation": ip_reputation_score,
            "proxy": ip_proxy_vpn,
            "datacenter": ip_datacenter
        },
        "behavior": session_data,
        "delivery": delivery_proof
    }

    evidence = Evidence(
        id=f"evd_{uuid.uuid4().hex[:16]}",
        transaction_id=txn.id,
        
        auth_method=auth_method,
        otp_verified=otp_verified,
        three_ds_version=three_ds_version,
        eci_value=eci_value,
        cavv=cavv,
        
        device_fingerprint=json.dumps(device_fingerprint),
        device_trust_score=device_trust_score,
        is_known_device=is_known_device,
        device_age_days=device_age_days,
        
        ip_reputation_score=ip_reputation_score,
        ip_proxy_vpn=ip_proxy_vpn,
        ip_tor=ip_tor,
        ip_datacenter=ip_datacenter,
        
        session_data=json.dumps(session_data),
        checkout_time_sec=checkout_time_sec,
        is_first_purchase=is_first_purchase,
        
        customer_lifetime_value=customer_lifetime_value,
        customer_total_orders=customer_total_orders,
        customer_dispute_rate=customer_dispute_rate,
        customer_days_since_last_order=customer_days_since_last_order,
        
        delivery_proof=json.dumps(delivery_proof) if delivery_proof else None,
        compiled_evidence=json.dumps(compiled_evidence),
        
        created_at=datetime.utcnow()
    )
    
    return evidence

def generate_evidence_bulk(transactions: List[Transaction]) -> List[Evidence]:
    """Generate evidence entries for a batch of transactions."""
    return [generate_evidence_for_transaction(txn) for txn in transactions]
