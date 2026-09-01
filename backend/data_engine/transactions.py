import random
import uuid
from typing import List
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy.orm import Session

from config import (
    INDIAN_BANKS,
    CARD_NETWORKS,
    UPI_APPS,
    MCC_CATEGORIES,
    DataGenerationConfig
)
from database.models import Transaction, Customer, Merchant

def generate_transactions(db: Session, config: DataGenerationConfig, customers: List[Customer], merchants: List[Merchant]) -> List[Transaction]:
    """
    Generate synthetic transactions.
    """
    np.random.seed(config.seed + 2)
    random.seed(config.seed + 2)
    
    transactions = []
    all_transactions = []
    
    num = config.num_transactions
    
    start_dt = datetime.strptime(config.start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(config.end_date, "%Y-%m-%d")
    date_range_sec = int((end_dt - start_dt).total_seconds())
    
    card_nets = list(CARD_NETWORKS.keys())
    card_weights = list(CARD_NETWORKS.values())
    
    customer_weights = [c.avg_monthly_spend for c in customers]
    merchant_weights = [m.monthly_volume for m in merchants]
    
    # Normalize weights
    cw_sum = sum(customer_weights)
    customer_weights = [w / cw_sum for w in customer_weights]
    
    mw_sum = sum(merchant_weights)
    merchant_weights = [w / mw_sum for w in merchant_weights]
    
    # Pre-select customers and merchants for all transactions based on weights
    selected_customers = np.random.choice(customers, size=num, p=customer_weights)
    selected_merchants = np.random.choice(merchants, size=num, p=merchant_weights)
    
    batch_size = 10000
    
    for i in range(num):
        customer = selected_customers[i]
        merchant = selected_merchants[i]
        
        tx_id = f"pay_{uuid.uuid4().hex[:14]}"
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        
        mcc_data = MCC_CATEGORIES[merchant.mcc_code]
        mean_amt = mcc_data["avg_txn"]
        std_amt = mcc_data["std_txn"]
        
        # log-normal amount based on MCC
        mu = np.log(mean_amt**2 / np.sqrt(mean_amt**2 + std_amt**2))
        sigma = np.sqrt(np.log(1 + (std_amt**2 / mean_amt**2)))
        amount_inr = max(10, np.random.lognormal(mu, sigma))
        amount_paise = int(amount_inr * 100)
        
        # Payment method
        if random.random() < 0.8:
            pm = customer.preferred_payment_method
        else:
            pm = random.choice(list(config.payment_methods.keys()))
            
        card_network = None
        card_issuer = None
        vpa = None
        upi_app = None
        auth_type = "pin"
        
        if pm in ["credit_card", "debit_card"]:
            card_network = random.choices(card_nets, weights=card_weights)[0]
            card_issuer = random.choice(INDIAN_BANKS)
            auth_type = "3ds"
        elif pm == "upi":
            username = customer.email.split("@")[0]
            bank_handle = random.choice(["okaxis", "ybl", "paytm", "apl"])
            vpa = f"{username}@{bank_handle}"
            upi_app = random.choice(UPI_APPS)
            auth_type = "otp"
            
        status = random.choices(["captured", "failed", "refunded"], weights=[0.95, 0.03, 0.02])[0]
        
        # Timestamps with diurnal patterns
        base_time = start_dt + timedelta(seconds=random.randint(0, date_range_sec))
        hour = base_time.hour
        
        # Adjust time for diurnal patterns
        # Morning peak 10-12, Evening peak 19-22, Low 2-6
        if 2 <= hour <= 6 and random.random() < 0.7:
            # Shift to peak
            base_time = base_time.replace(hour=random.choice([10, 11, 19, 20, 21]))
            
        # Geo-IP match
        geo_ip_match = random.random() < 0.90
        
        billing_city = customer.city
        if random.random() < 0.15:
            billing_city = random.choice(INDIAN_BANKS) # random other city, just mock
            
        delivery_carrier = random.choice(["Delhivery", "BlueDart", "DTDC", "India Post"])
            
        tx = Transaction(
            id=tx_id,
            order_id=order_id,
            customer_id=customer.id,
            merchant_id=merchant.id,
            amount=amount_paise,
            currency="INR",
            payment_method=pm,
            card_network=card_network,
            card_issuer=card_issuer,
            card_last4=str(random.randint(1000, 9999)) if pm in ["credit_card", "debit_card"] else None,
            vpa=vpa,
            upi_app=upi_app,
            status=status,
            auth_type=auth_type,
            rrn=str(random.randint(100000000000, 999999999999)),
            auth_code=str(random.randint(100000, 999999)),
            device_id=customer.primary_device_id,
            ip_address=f"{random.choice([103, 49, 157])}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
            session_duration_sec=random.randint(30, 600),
            pages_viewed=random.randint(1, 15),
            geo_ip_match=geo_ip_match,
            billing_city=billing_city,
            shipping_city=customer.city,
            delivery_carrier=delivery_carrier,
            delivery_tracking_id=f"TRK{uuid.uuid4().hex[:8].upper()}",
            delivery_status="delivered",
            created_at=base_time,
            captured_at=base_time + timedelta(seconds=random.randint(1, 10)) if status == "captured" else None
        )
        transactions.append(tx)
        
        if len(transactions) >= batch_size:
            db.bulk_save_objects(transactions)
            db.commit()
            all_transactions.extend(transactions)
            transactions = []
            
    if transactions:
        db.bulk_save_objects(transactions)
        db.commit()
        all_transactions.extend(transactions)
        
    return all_transactions
