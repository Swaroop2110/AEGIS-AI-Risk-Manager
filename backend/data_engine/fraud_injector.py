import uuid
import random
from datetime import timedelta
from typing import List, Tuple, Dict, Any
import numpy as np

from database.models import (
    Transaction, Customer, Merchant, Dispute, 
    TransactionStatus, FraudType, DisputePhase, DisputeStatus
)
from config import DataGenerationConfig, INDIAN_CITIES, data_config

def _generate_ip() -> str:
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

def _generate_vpn_ip() -> str:
    # Typical VPN IP ranges (mocked)
    prefixes = ["104.28", "145.239", "185.105", "194.35", "45.134"]
    return f"{random.choice(prefixes)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

def _generate_card() -> Tuple[str, str, str, str]:
    networks = ["Visa", "Mastercard", "RuPay"]
    issuers = ["HDFC", "ICICI", "SBI", "Axis", "Kotak"]
    types = ["credit", "debit"]
    return (
        random.choice(networks),
        random.choice(issuers),
        str(random.randint(1000, 9999)),
        random.choice(types)
    )

def inject_fraud(
    transactions: List[Transaction],
    customers: List[Customer],
    merchants: List[Merchant],
    config: DataGenerationConfig = None,
    target_fraud_count: int = None,
) -> Dict[str, Any]:
    """
    Takes generated legitimate transactions and injects realistic fraud patterns.
    Returns a dictionary containing the updated transactions, generated disputes, and statistics.
    """
    config = config or data_config
    random.seed(config.seed)
    np.random.seed(config.seed)

    # We will modify the transactions list in-place where needed, and append new transactions.
    total_txns = len(transactions)
    if target_fraud_count is None:
        target_fraud_count = int(total_txns * config.fraud_rate)
    
    # Calculate target counts per vector
    vector_weights = {
        "velocity": config.velocity_attack_pct,
        "mule": config.mule_ring_pct,
        "friendly": config.friendly_fraud_pct,
        "spoofing": config.device_spoofing_pct,
        "ato": config.account_takeover_pct,
    }
    raw_counts = {name: target_fraud_count * weight for name, weight in vector_weights.items()}
    counts = {name: int(value) for name, value in raw_counts.items()}
    remaining = target_fraud_count - sum(counts.values())
    for name in sorted(raw_counts, key=lambda item: raw_counts[item] - counts[item], reverse=True):
        if remaining <= 0:
            break
        counts[name] += 1
        remaining -= 1
    
    injected_txns = []
    generated_disputes = []
    rings_created = 0
    
    stats = {
        "total_fraud": 0,
        "by_vector": {k: 0 for k in counts.keys()},
        "rings_created": 0,
        "disputes_generated": 0
    }

    # Helper to create base fraud transaction
    def _create_base_txn(cust: Customer, merch: Merchant, amount_inr: int, ts, ring_id: str = None) -> Transaction:
        return Transaction(
            id=f"pay_{uuid.uuid4().hex[:12]}",
            order_id=f"ord_{uuid.uuid4().hex[:12]}",
            customer_id=cust.id,
            merchant_id=merch.id,
            amount=amount_inr * 100,
            currency="INR",
            created_at=ts,
            captured_at=ts + timedelta(seconds=random.randint(2, 10)),
            is_fraud=True,
            fraud_ring_id=ring_id,
            geo_lat=cust.latitude,
            geo_lon=cust.longitude,
            billing_city=cust.city,
            shipping_city=cust.city,
            geo_ip_match=True
        )

    # --- Vector A: Velocity Attack (Carding) ---
    # 15-25 rapid micro-transactions (10-500) within 2 mins
    while stats["by_vector"]["velocity"] < counts["velocity"]:
        ring_id = str(uuid.uuid4())
        rings_created += 1
        num_attempts = min(random.randint(15, 25), counts["velocity"] - stats["by_vector"]["velocity"])
        base_cust = random.choice(customers)
        base_device = str(uuid.uuid4())
        base_ts = transactions[random.randint(0, len(transactions)-1)].created_at
        
        for i in range(num_attempts):
            merch = random.choice(merchants)
            amt = random.randint(10, 500)
            txn_ts = base_ts + timedelta(seconds=i * random.randint(1, 8))
            
            txn = _create_base_txn(base_cust, merch, amt, txn_ts, ring_id)
            txn.fraud_type = FraudType.VELOCITY_ATTACK.value
            txn.device_id = base_device
            txn.ip_address = _generate_vpn_ip()
            txn.ip_city = "Unknown"
            txn.geo_ip_match = False
            txn.payment_method = "credit_card"
            txn.card_network, txn.card_issuer, txn.card_last4, txn.card_type = _generate_card()
            
            # 90% fail, 10% succeed
            if random.random() < 0.90:
                txn.status = TransactionStatus.FAILED.value
                txn.captured_at = None
            else:
                txn.status = TransactionStatus.CAPTURED.value
                
                # Create dispute for successful ones
                disp = Dispute(
                    id=f"disp_{uuid.uuid4().hex[:12]}",
                    transaction_id=txn.id,
                    amount=txn.amount,
                    reason_code="10.4" if txn.card_network == "Visa" else "4837",
                    phase=DisputePhase.CHARGEBACK.value,
                    status=DisputeStatus.OPEN.value,
                    created_at=txn.created_at + timedelta(days=random.randint(5, 15))
                )
                generated_disputes.append(disp)
                stats["disputes_generated"] += 1
                
            injected_txns.append(txn)
            stats["by_vector"]["velocity"] += 1
            stats["total_fraud"] += 1

    # --- Vector B: Mule Ring Layering ---
    while stats["by_vector"]["mule"] < counts["mule"]:
        ring_id = str(uuid.uuid4())
        rings_created += 1
        num_mules = min(random.randint(4, 8), len(customers))
        
        # Select mules (< 30 days age approximation, we just pick random for now)
        mules = random.sample(customers, num_mules)
        base_ts = transactions[random.randint(0, len(transactions)-1)].created_at
        
        # A -> B, C, D
        a = mules[0]
        initial_amt = random.randint(10000, 50000)
        
        # Chain generation
        for i in range(len(mules)):
            if stats["by_vector"]["mule"] >= counts["mule"]:
                break
            sender = mules[i]
            receivers = [mules[(i + 1) % len(mules)], mules[(i + 2) % len(mules)]]
            
            for receiver in receivers:
                if stats["by_vector"]["mule"] >= counts["mule"]:
                    break
                merch = random.choice(merchants) # Using merchant as a sink/proxy for now
                txn_ts = base_ts + timedelta(minutes=random.randint(1, 60))
                txn = _create_base_txn(sender, merch, random.randint(1000, 5000), txn_ts, ring_id)
                txn.fraud_type = FraudType.MULE_RING.value
                txn.payment_method = "upi"
                txn.vpa = f"{receiver.phone}@upi"
                txn.status = TransactionStatus.CAPTURED.value
                txn.ip_address = _generate_ip()
                txn.device_id = str(uuid.uuid4())
                
                injected_txns.append(txn)
                stats["by_vector"]["mule"] += 1
                stats["total_fraud"] += 1

    # --- Vector C: Friendly Fraud ---
    # Most common. Pick legit customers, 5000-50000 amt, dispute 20-60 days later
    good_customers = [c for c in customers if c.total_transactions >= 5]
    if not good_customers:
        good_customers = customers

    while stats["by_vector"]["friendly"] < counts["friendly"]:
        cust = random.choice(good_customers)
        merch = random.choice(merchants)
        amt = random.randint(5000, 50000)
        txn_ts = transactions[random.randint(0, len(transactions)-1)].created_at
        
        txn = _create_base_txn(cust, merch, amt, txn_ts)
        txn.fraud_type = FraudType.FRIENDLY_FRAUD.value
        txn.status = TransactionStatus.CAPTURED.value
        txn.payment_method = "credit_card"
        txn.card_network, txn.card_issuer, txn.card_last4, txn.card_type = _generate_card()
        txn.auth_type = "3ds"
        txn.device_id = cust.primary_device_id or str(uuid.uuid4())
        txn.ip_address = _generate_ip()
        
        # Delivery confirmed
        txn.delivery_status = "delivered"
        txn.delivery_signed = True
        txn.delivery_timestamp = txn_ts + timedelta(days=random.randint(1, 5))
        
        injected_txns.append(txn)
        
        # Update customer stats
        cust.dispute_count += 1
        
        # Dispute
        disp = Dispute(
            id=f"disp_{uuid.uuid4().hex[:12]}",
            transaction_id=txn.id,
            amount=txn.amount,
            reason_code="13.1" if txn.card_network == "Visa" else "4853",
            phase=DisputePhase.CHARGEBACK.value,
            status=DisputeStatus.OPEN.value,
            created_at=txn.created_at + timedelta(days=random.randint(20, 60))
        )
        generated_disputes.append(disp)
        
        stats["by_vector"]["friendly"] += 1
        stats["total_fraud"] += 1
        stats["disputes_generated"] += 1

    # --- Vector D: Device Spoofing Ring ---
    high_value_mccs = ["5732", "5944", "5045"] # Electronics, Jewelry, Computers
    hv_merchants = [m for m in merchants if m.mcc_code in high_value_mccs]
    if not hv_merchants:
        hv_merchants = merchants

    while stats["by_vector"]["spoofing"] < counts["spoofing"]:
        ring_id = str(uuid.uuid4())
        rings_created += 1
        shared_device_id = str(uuid.uuid4())
        num_accounts = random.randint(10, 20)
        ring_customers = random.sample(customers, min(num_accounts, len(customers)))
        base_ts = transactions[random.randint(0, len(transactions)-1)].created_at
        
        for rc in ring_customers:
            if stats["by_vector"]["spoofing"] >= counts["spoofing"]:
                break
            num_txns = random.randint(1, 3)
            for _ in range(num_txns):
                if stats["by_vector"]["spoofing"] >= counts["spoofing"]:
                    break
                merch = random.choice(hv_merchants)
                amt = random.randint(1000, 25000)
                txn_ts = base_ts + timedelta(hours=random.randint(1, 48))
                
                txn = _create_base_txn(rc, merch, amt, txn_ts, ring_id)
                txn.fraud_type = FraudType.DEVICE_SPOOFING.value
                txn.status = TransactionStatus.CAPTURED.value
                txn.device_id = shared_device_id
                txn.payment_method = random.choice(["credit_card", "upi", "wallet"])
                txn.user_agent = f"Mozilla/5.0 (Spoofed Variant {random.randint(1, 100)})"
                txn.ip_address = _generate_vpn_ip()
                txn.geo_ip_match = False
                
                injected_txns.append(txn)
                stats["by_vector"]["spoofing"] += 1
                stats["total_fraud"] += 1

    # --- Vector E: Account Takeover (ATO) ---
    while stats["by_vector"]["ato"] < counts["ato"]:
        ring_id = str(uuid.uuid4())
        rings_created += 1
        cust = random.choice(good_customers)
        num_txns = random.randint(2, 5)
        base_ts = transactions[random.randint(0, len(transactions)-1)].created_at
        
        ato_device_id = str(uuid.uuid4())
        ato_ip = _generate_ip()
        
        for i in range(num_txns):
            if stats["by_vector"]["ato"] >= counts["ato"]:
                break
            merch = random.choice(merchants)
            amt = random.randint(int(cust.avg_monthly_spend * 3), int(cust.avg_monthly_spend * 10) + 1000)
            txn_ts = base_ts + timedelta(hours=3, minutes=i*15) # 3 AM typically
            
            txn = _create_base_txn(cust, merch, amt, txn_ts, ring_id)
            txn.fraud_type = FraudType.ACCOUNT_TAKEOVER.value
            txn.status = TransactionStatus.CAPTURED.value
            txn.device_id = ato_device_id
            txn.ip_address = ato_ip
            txn.ip_city = random.choice([c["city"] for c in INDIAN_CITIES["tier_1"]]) # Different city
            txn.geo_ip_match = False
            txn.payment_method = "credit_card"
            txn.card_network, txn.card_issuer, txn.card_last4, txn.card_type = _generate_card()
            
            injected_txns.append(txn)
            stats["by_vector"]["ato"] += 1
            stats["total_fraud"] += 1
            
            # Create dispute
            disp = Dispute(
                id=f"disp_{uuid.uuid4().hex[:12]}",
                transaction_id=txn.id,
                amount=txn.amount,
                reason_code="10.4" if txn.card_network == "Visa" else "4837",
                phase=DisputePhase.CHARGEBACK.value,
                status=DisputeStatus.OPEN.value,
                created_at=txn.created_at + timedelta(days=random.randint(10, 30))
            )
            generated_disputes.append(disp)
            stats["disputes_generated"] += 1

    stats["rings_created"] = rings_created
    
    # Combine original transactions with injected fraud
    combined_txns = transactions + injected_txns
    
    # Sort combined by created_at to maintain realistic timeline
    combined_txns.sort(key=lambda x: x.created_at)

    return {
        "transactions": combined_txns,
        "injected_transactions": injected_txns,
        "disputes": generated_disputes,
        "stats": stats
    }
