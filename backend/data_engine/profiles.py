import random
import uuid
import hashlib
from typing import List, Dict, Any
from datetime import datetime, timedelta
import numpy as np
from faker import Faker
from sqlalchemy.orm import Session

from config import (
    INDIAN_CITIES,
    MCC_CATEGORIES,
    DataGenerationConfig
)
from database.models import Customer, Merchant

fake = Faker('en_IN')

# Device models pool for Indian market
DEVICE_MODELS = [
    "Samsung Galaxy S23", "Samsung Galaxy M14", "iPhone 14", "iPhone 13",
    "OnePlus 11", "OnePlus Nord CE 3", "Redmi Note 12", "Xiaomi 13 Pro",
    "Google Pixel 7a", "Vivo V27", "Oppo Reno 10", "Realme 11 Pro"
]

def generate_customers(db: Session, config: DataGenerationConfig) -> List[Customer]:
    """
    Generate synthetic customer profiles for the Indian market.
    """
    np.random.seed(config.seed)
    random.seed(config.seed)
    
    customers = []
    
    # Flatten city pools
    tier_1 = INDIAN_CITIES["tier_1"]
    tier_2 = INDIAN_CITIES["tier_2"]
    tier_3 = INDIAN_CITIES["tier_3"]
    
    # Payment methods and weights
    pay_methods = list(config.payment_methods.keys())
    pay_weights = list(config.payment_methods.values())
    
    # Generate properties
    num = config.num_customers
    
    for i in range(num):
        customer_id = str(uuid.uuid4())
        name = fake.name()
        email = f"{name.lower().replace(' ', '.')}@example.com"
        phone = f"+91{random.randint(6000000000, 9999999999)}"
        
        # City selection (60%, 30%, 10%)
        tier_choice = random.choices(["tier_1", "tier_2", "tier_3"], weights=[0.60, 0.30, 0.10])[0]
        if tier_choice == "tier_1":
            city_data = random.choice(tier_1)
            tier_int = 1
            spend_mean = np.log(7000)
        elif tier_choice == "tier_2":
            city_data = random.choice(tier_2)
            tier_int = 2
            spend_mean = np.log(4500)
        else:
            city_data = random.choice(tier_3)
            tier_int = 3
            spend_mean = np.log(2500)
            
        avg_monthly_spend = np.random.lognormal(mean=spend_mean, sigma=0.5)
        
        # Payment method
        preferred_payment_method = random.choices(pay_methods, weights=pay_weights)[0]
        
        # Account age (exponential)
        account_age_days = int(np.random.exponential(scale=300))
        account_age_days = max(1, min(1800, account_age_days))
        
        # Device
        device_model = random.choice(DEVICE_MODELS)
        device_os = "iOS" if "iPhone" in device_model else "Android"
        device_id_raw = f"{customer_id}-{device_model}-{device_os}"
        primary_device_id = hashlib.sha256(device_id_raw.encode()).hexdigest()
        
        # Risk tier
        risk_tier = random.choices(["normal", "watch", "high_risk"], weights=[0.95, 0.04, 0.01])[0]
        
        customer = Customer(
            id=customer_id,
            name=name,
            email=email,
            phone=phone,
            city=city_data["city"],
            state=city_data["state"],
            city_tier=tier_int,
            latitude=city_data["lat"],
            longitude=city_data["lon"],
            avg_monthly_spend=float(avg_monthly_spend),
            preferred_payment_method=preferred_payment_method,
            account_age_days=account_age_days,
            total_transactions=0,
            dispute_count=0,
            risk_tier=risk_tier,
            primary_device_id=primary_device_id,
            primary_device_model=device_model,
            primary_device_os=device_os,
            created_at=datetime.utcnow() - timedelta(days=account_age_days)
        )
        customers.append(customer)
        
    # Bulk insert
    db.bulk_save_objects(customers)
    db.commit()
    
    return customers


def generate_merchants(db: Session, config: DataGenerationConfig) -> List[Merchant]:
    """
    Generate synthetic merchant profiles.
    """
    np.random.seed(config.seed + 1)
    random.seed(config.seed + 1)
    
    merchants = []
    
    tier_1 = INDIAN_CITIES["tier_1"]
    tier_2 = INDIAN_CITIES["tier_2"]
    tier_3 = INDIAN_CITIES["tier_3"]
    
    mcc_keys = list(MCC_CATEGORIES.keys())
    
    business_suffixes = ["Electronics", "Grocers", "Retail", "Services", "Mart", "Supermarket", "Boutique"]
    
    num = config.num_merchants
    
    for i in range(num):
        merchant_id = str(uuid.uuid4())
        
        mcc_code = random.choice(mcc_keys)
        mcc_data = MCC_CATEGORIES[mcc_code]
        
        biz_type = random.choice(business_suffixes)
        name = f"{fake.last_name()} {biz_type}"
        
        # City selection (80%, 15%, 5%)
        tier_choice = random.choices(["tier_1", "tier_2", "tier_3"], weights=[0.80, 0.15, 0.05])[0]
        if tier_choice == "tier_1":
            city_data = random.choice(tier_1)
        elif tier_choice == "tier_2":
            city_data = random.choice(tier_2)
        else:
            city_data = random.choice(tier_3)
            
        # Avg ticket size with noise
        avg_ticket = max(10, np.random.normal(mcc_data["avg_txn"], mcc_data["std_txn"] * 0.2))
        
        # Volume
        monthly_volume = int(np.random.uniform(100, 50000))
        
        # Business type
        business_type = random.choices(["online", "hybrid", "offline"], weights=[0.60, 0.30, 0.10])[0]
        
        # Days active
        days_active = random.randint(30, 2000)
        
        merchant = Merchant(
            id=merchant_id,
            name=name,
            mcc_code=mcc_code,
            mcc_category=mcc_data["name"],
            city=city_data["city"],
            state=city_data["state"],
            avg_ticket_size=float(avg_ticket),
            monthly_volume=monthly_volume,
            chargeback_rate=random.uniform(0.001, 0.02),
            business_type=business_type,
            risk_category="standard",
            days_active=days_active,
            created_at=datetime.utcnow() - timedelta(days=days_active)
        )
        merchants.append(merchant)
        
    db.bulk_save_objects(merchants)
    db.commit()
    
    return merchants
