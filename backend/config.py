"""
AEGIS Configuration — Central settings for the entire platform.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# === Paths ===
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
MODELS_DIR = DATA_DIR / "models"
EVIDENCE_DIR = DATA_DIR / "evidence"
DB_PATH = DATA_DIR / "aegis.db"

# Create directories
for d in [DATA_DIR, SYNTHETIC_DIR, MODELS_DIR, EVIDENCE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class DataGenerationConfig:
    """Configuration for synthetic data generation."""
    num_customers: int = 10_000
    num_merchants: int = 500
    num_transactions: int = 100_000
    fraud_rate: float = 0.02  # 2% overall fraud rate
    
    # Fraud vector distribution (of total fraud transactions)
    velocity_attack_pct: float = 0.25
    mule_ring_pct: float = 0.20
    friendly_fraud_pct: float = 0.30
    device_spoofing_pct: float = 0.15
    account_takeover_pct: float = 0.10
    
    # Time range for transactions (Unix timestamps)
    start_date: str = "2026-01-01"
    end_date: str = "2026-08-28"
    
    # Indian payment method distribution
    payment_methods: dict = field(default_factory=lambda: {
        "upi": 0.55,
        "credit_card": 0.15,
        "debit_card": 0.20,
        "wallet": 0.07,
        "netbanking": 0.03,
    })
    
    # Random seed for reproducibility
    seed: int = 42


@dataclass
class ModelConfig:
    """Configuration for ML models."""
    # L1: LightGBM
    lgbm_num_leaves: int = 63
    lgbm_learning_rate: float = 0.05
    lgbm_n_estimators: int = 300
    lgbm_min_child_samples: int = 20
    
    # L2: GNN
    gnn_hidden_channels: int = 128
    gnn_num_layers: int = 3
    gnn_dropout: float = 0.3
    gnn_learning_rate: float = 0.001
    gnn_epochs: int = 100
    gnn_batch_size: int = 256
    
    # Train/test split
    test_size: float = 0.20
    val_size: float = 0.10
    
    # Scoring thresholds
    l1_fast_threshold: float = 0.35  # Above this → escalate to L2 (was 0.5, lowered for better recall)
    high_risk_threshold: float = 0.60  # Above this → block/flag (was 0.7)
    low_risk_threshold: float = 0.20  # Below this → safe (was 0.3)


@dataclass
class DisputeConfig:
    """Configuration for dispute defense engine."""
    # Win probability thresholds
    auto_defend_threshold: float = 0.7    # Auto-file representment
    review_threshold: float = 0.4         # File with merchant review
    accept_threshold: float = 0.4         # Below this → accept chargeback
    
    # Arbitration fee (in INR)
    arbitration_fee: int = 40_000  # ~$500
    
    # LLM settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "template")  # "openai", "gemini", "template"
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")


@dataclass  
class ServerConfig:
    """Configuration for FastAPI server."""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    cors_origins: list = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ])


# === Global Config Instances ===
data_config = DataGenerationConfig()
model_config = ModelConfig()
dispute_config = DisputeConfig()
server_config = ServerConfig()


# === MCC (Merchant Category Codes) for Indian Commerce ===
MCC_CATEGORIES = {
    "5411": {"name": "Grocery Stores", "avg_txn": 850, "std_txn": 500},
    "5812": {"name": "Restaurants", "avg_txn": 600, "std_txn": 350},
    "5691": {"name": "Clothing Stores", "avg_txn": 2500, "std_txn": 1800},
    "5732": {"name": "Electronics", "avg_txn": 15000, "std_txn": 12000},
    "5944": {"name": "Jewelry Stores", "avg_txn": 25000, "std_txn": 20000},
    "5999": {"name": "Miscellaneous Retail", "avg_txn": 1200, "std_txn": 900},
    "4814": {"name": "Telecom Services", "avg_txn": 500, "std_txn": 300},
    "7011": {"name": "Hotels & Lodging", "avg_txn": 5000, "std_txn": 4000},
    "4511": {"name": "Airlines", "avg_txn": 8000, "std_txn": 6000},
    "5311": {"name": "Department Stores", "avg_txn": 3000, "std_txn": 2500},
    "5912": {"name": "Pharmacy", "avg_txn": 400, "std_txn": 250},
    "5814": {"name": "Fast Food", "avg_txn": 350, "std_txn": 200},
    "7832": {"name": "Movie Theatres", "avg_txn": 600, "std_txn": 300},
    "5045": {"name": "Computers & Software", "avg_txn": 20000, "std_txn": 15000},
    "5947": {"name": "Gift & Card Shops", "avg_txn": 1500, "std_txn": 1000},
}

# === Indian Cities with Tier Classification ===
INDIAN_CITIES = {
    "tier_1": [
        {"city": "Mumbai", "state": "Maharashtra", "lat": 19.076, "lon": 72.877},
        {"city": "Delhi", "state": "Delhi", "lat": 28.613, "lon": 77.209},
        {"city": "Bangalore", "state": "Karnataka", "lat": 12.971, "lon": 77.594},
        {"city": "Hyderabad", "state": "Telangana", "lat": 17.385, "lon": 78.486},
        {"city": "Chennai", "state": "Tamil Nadu", "lat": 13.082, "lon": 80.270},
        {"city": "Kolkata", "state": "West Bengal", "lat": 22.572, "lon": 88.363},
        {"city": "Pune", "state": "Maharashtra", "lat": 18.520, "lon": 73.856},
        {"city": "Ahmedabad", "state": "Gujarat", "lat": 23.022, "lon": 72.571},
    ],
    "tier_2": [
        {"city": "Jaipur", "state": "Rajasthan", "lat": 26.912, "lon": 75.787},
        {"city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.846, "lon": 80.946},
        {"city": "Chandigarh", "state": "Punjab", "lat": 30.733, "lon": 76.779},
        {"city": "Indore", "state": "Madhya Pradesh", "lat": 22.719, "lon": 75.857},
        {"city": "Kochi", "state": "Kerala", "lat": 9.931, "lon": 76.267},
        {"city": "Coimbatore", "state": "Tamil Nadu", "lat": 11.016, "lon": 76.955},
        {"city": "Nagpur", "state": "Maharashtra", "lat": 21.145, "lon": 79.088},
        {"city": "Bhopal", "state": "Madhya Pradesh", "lat": 23.259, "lon": 77.412},
        {"city": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.686, "lon": 83.218},
        {"city": "Patna", "state": "Bihar", "lat": 25.611, "lon": 85.144},
    ],
    "tier_3": [
        {"city": "Varanasi", "state": "Uttar Pradesh", "lat": 25.317, "lon": 82.987},
        {"city": "Udaipur", "state": "Rajasthan", "lat": 24.585, "lon": 73.712},
        {"city": "Dehradun", "state": "Uttarakhand", "lat": 30.316, "lon": 78.032},
        {"city": "Guwahati", "state": "Assam", "lat": 26.148, "lon": 91.731},
        {"city": "Mysore", "state": "Karnataka", "lat": 12.295, "lon": 76.639},
        {"city": "Mangalore", "state": "Karnataka", "lat": 12.914, "lon": 74.856},
        {"city": "Ranchi", "state": "Jharkhand", "lat": 23.344, "lon": 85.309},
        {"city": "Raipur", "state": "Chhattisgarh", "lat": 21.251, "lon": 81.629},
    ],
}

# === Indian Bank Issuers ===
INDIAN_BANKS = [
    "HDFC", "ICICI", "SBI", "Axis", "Kotak", "IndusInd", 
    "Yes Bank", "PNB", "Bank of Baroda", "Canara Bank",
    "Union Bank", "IDBI", "Federal Bank", "RBL Bank",
]

# === Card Networks ===
CARD_NETWORKS = {
    "Visa": 0.35,
    "Mastercard": 0.30,
    "RuPay": 0.35,
}

# === UPI Apps ===
UPI_APPS = [
    "GooglePay", "PhonePe", "Paytm", "BHIM", "AmazonPay",
    "WhatsApp Pay", "CRED", "Jupiter", "Slice",
]
