"""
AEGIS Database Models — SQLAlchemy ORM models for the core data schema.

Tables:
- customers: Simulated customer profiles with Indian demographics
- merchants: Merchant profiles with MCC codes
- transactions: Payment transactions (legitimate + fraudulent)
- devices: Device fingerprint records
- disputes: Chargeback/dispute records
- evidence: Evidence vault — signals captured at auth-time
- risk_scores: ML scoring results for each transaction
- graph_edges: Heterogeneous graph edge records for GNN
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, Enum as SQLEnum, BigInteger
)
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime
import enum


class Base(DeclarativeBase):
    pass


# === Enums ===

class PaymentMethod(str, enum.Enum):
    UPI = "upi"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    WALLET = "wallet"
    NETBANKING = "netbanking"


class TransactionStatus(str, enum.Enum):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class FraudType(str, enum.Enum):
    LEGITIMATE = "legitimate"
    VELOCITY_ATTACK = "velocity_attack"
    MULE_RING = "mule_ring"
    FRIENDLY_FRAUD = "friendly_fraud"
    DEVICE_SPOOFING = "device_spoofing"
    ACCOUNT_TAKEOVER = "account_takeover"


class DisputePhase(str, enum.Enum):
    RETRIEVAL = "retrieval"
    FRAUD_NOTIFICATION = "fraud_notification"
    CHARGEBACK = "chargeback"
    PRE_ARBITRATION = "pre_arbitration"
    ARBITRATION = "arbitration"


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    ACTION_REQUIRED = "action_required"
    WON = "won"
    LOST = "lost"
    CLOSED = "closed"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# === Models ===

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False)
    phone = Column(String(15), nullable=False)
    city = Column(String(50), nullable=False)
    state = Column(String(50), nullable=False)
    city_tier = Column(Integer, nullable=False)  # 1, 2, or 3
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Behavioral profile
    avg_monthly_spend = Column(Float, default=0)
    preferred_payment_method = Column(String(20))
    account_age_days = Column(Integer, default=0)
    total_transactions = Column(Integer, default=0)
    dispute_count = Column(Integer, default=0)
    risk_tier = Column(String(10), default="normal")  # normal, watch, high_risk
    
    # Device info (primary device)
    primary_device_id = Column(String(64))
    primary_device_model = Column(String(50))
    primary_device_os = Column(String(30))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="customer")
    
    __table_args__ = (
        Index("idx_customer_city", "city"),
        Index("idx_customer_risk", "risk_tier"),
    )


class Merchant(Base):
    __tablename__ = "merchants"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    mcc_code = Column(String(4), nullable=False)
    mcc_category = Column(String(50), nullable=False)
    city = Column(String(50), nullable=False)
    state = Column(String(50), nullable=False)
    
    # Business profile
    avg_ticket_size = Column(Float, default=0)
    monthly_volume = Column(Integer, default=0)
    chargeback_rate = Column(Float, default=0)
    business_type = Column(String(20), default="online")  # online, offline, hybrid
    
    # Risk profile
    risk_category = Column(String(20), default="standard")  # low, standard, high, restricted
    days_active = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="merchant")
    
    __table_args__ = (
        Index("idx_merchant_mcc", "mcc_code"),
    )


class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String(64), primary_key=True)  # Device fingerprint hash
    device_model = Column(String(50))
    device_brand = Column(String(30))
    os_name = Column(String(20))
    os_version = Column(String(20))
    screen_resolution = Column(String(20))
    language = Column(String(10))
    timezone = Column(String(40))
    is_emulator = Column(Boolean, default=False)
    is_rooted = Column(Boolean, default=False)
    
    # Usage tracking
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    num_unique_users = Column(Integer, default=1)
    num_transactions = Column(Integer, default=0)
    
    # Risk flags
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String(100))


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String(36), primary_key=True)  # pay_xxxxx format
    order_id = Column(String(36))
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False)
    merchant_id = Column(String(36), ForeignKey("merchants.id"), nullable=False)
    
    # Payment details
    amount = Column(BigInteger, nullable=False)  # Amount in paise (INR * 100)
    currency = Column(String(3), default="INR")
    payment_method = Column(String(20), nullable=False)
    card_network = Column(String(20))  # Visa, Mastercard, RuPay
    card_issuer = Column(String(30))   # HDFC, ICICI, etc.
    card_last4 = Column(String(4))
    card_type = Column(String(10))     # credit, debit
    vpa = Column(String(50))           # UPI VPA (user@bank)
    upi_app = Column(String(20))       # GooglePay, PhonePe, etc.
    wallet_name = Column(String(20))
    
    # Auth details
    status = Column(String(20), default="captured")
    is_international = Column(Boolean, default=False)
    auth_type = Column(String(20))     # 3ds, otp, biometric, pin
    eci_indicator = Column(String(5))  # 3DS ECI value (05, 02, 07)
    auth_code = Column(String(10))
    rrn = Column(String(20))          # Retrieval Reference Number
    
    # Context signals (captured at auth-time for evidence vault)
    device_id = Column(String(64))
    ip_address = Column(String(45))
    ip_city = Column(String(50))
    ip_country = Column(String(5), default="IN")
    ip_isp = Column(String(50))
    user_agent = Column(String(200))
    session_duration_sec = Column(Integer)
    pages_viewed = Column(Integer)
    
    # Geolocation
    geo_lat = Column(Float)
    geo_lon = Column(Float)
    billing_city = Column(String(50))
    shipping_city = Column(String(50))
    geo_ip_match = Column(Boolean)  # Does IP location match billing city?
    
    # Timestamps
    created_at = Column(DateTime, nullable=False)
    captured_at = Column(DateTime)
    
    # === GROUND TRUTH LABELS (for ML training) ===
    is_fraud = Column(Boolean, default=False)
    fraud_type = Column(String(30), default="legitimate")
    fraud_ring_id = Column(String(36))  # Links related fraudulent transactions
    
    # Delivery info (for chargeback evidence)
    delivery_status = Column(String(20))  # shipped, delivered, returned
    delivery_carrier = Column(String(30))
    delivery_tracking_id = Column(String(50))
    delivery_timestamp = Column(DateTime)
    delivery_gps_lat = Column(Float)
    delivery_gps_lon = Column(Float)
    delivery_signed = Column(Boolean)
    
    # Relationships
    customer = relationship("Customer", back_populates="transactions")
    merchant = relationship("Merchant", back_populates="transactions")
    risk_scores = relationship("RiskScore", back_populates="transaction")
    dispute = relationship("Dispute", back_populates="transaction", uselist=False)
    evidence = relationship("Evidence", back_populates="transaction", uselist=False)
    
    __table_args__ = (
        Index("idx_txn_customer", "customer_id"),
        Index("idx_txn_merchant", "merchant_id"),
        Index("idx_txn_device", "device_id"),
        Index("idx_txn_created", "created_at"),
        Index("idx_txn_fraud", "is_fraud"),
        Index("idx_txn_fraud_type", "fraud_type"),
        Index("idx_txn_ip", "ip_address"),
        Index("idx_txn_ring", "fraud_ring_id"),
    )


class Dispute(Base):
    __tablename__ = "disputes"
    
    id = Column(String(36), primary_key=True)  # disp_xxxxx format
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False)
    
    # Dispute details
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), default="INR")
    reason_code = Column(String(10), nullable=False)
    reason_description = Column(Text)
    card_network = Column(String(20))  # Which scheme's reason code
    
    # Lifecycle
    phase = Column(String(20), default="chargeback")
    status = Column(String(20), default="open")
    respond_by = Column(DateTime)
    
    # AEGIS defense results
    win_probability = Column(Float)
    recommended_action = Column(String(20))  # auto_defend, review, accept
    evidence_completeness = Column(Float)  # 0.0 - 1.0
    defense_strategy = Column(Text)  # JSON strategy from Agent 2
    evidence_pdf_path = Column(String(200))
    
    # Outcome
    actual_outcome = Column(String(10))  # won, lost
    amount_recovered = Column(BigInteger, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime)
    resolved_at = Column(DateTime)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="dispute")
    
    __table_args__ = (
        Index("idx_dispute_status", "status"),
        Index("idx_dispute_phase", "phase"),
        Index("idx_dispute_reason", "reason_code"),
    )


class Evidence(Base):
    """Evidence Vault — stores all auth-time signals for future dispute defense."""
    __tablename__ = "evidence"
    
    id = Column(String(36), primary_key=True)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False, unique=True)
    
    # Authentication evidence
    auth_method = Column(String(20))
    otp_verified = Column(Boolean)
    three_ds_version = Column(String(5))
    eci_value = Column(String(5))
    cavv = Column(String(50))  # Cardholder Authentication Verification Value
    
    # Device intelligence
    device_fingerprint = Column(Text)  # JSON blob of device details
    device_trust_score = Column(Float)
    is_known_device = Column(Boolean)
    device_age_days = Column(Integer)
    
    # Network intelligence
    ip_reputation_score = Column(Float)
    ip_proxy_vpn = Column(Boolean)
    ip_tor = Column(Boolean)
    ip_datacenter = Column(Boolean)
    
    # Behavioral signals
    session_data = Column(Text)  # JSON: time_on_page, click_count, scroll_depth, etc.
    checkout_time_sec = Column(Integer)
    is_first_purchase = Column(Boolean)
    
    # Customer history snapshot (at time of transaction)
    customer_lifetime_value = Column(Float)
    customer_total_orders = Column(Integer)
    customer_dispute_rate = Column(Float)
    customer_days_since_last_order = Column(Integer)
    
    # Delivery evidence
    delivery_proof = Column(Text)  # JSON: carrier data, GPS, signature URL
    
    # Compiled evidence package
    compiled_evidence = Column(Text)  # JSON: full evidence bundle for dispute
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="evidence")
    
    __table_args__ = (
        Index("idx_evidence_txn", "transaction_id"),
    )


class RiskScore(Base):
    """ML scoring results for each transaction."""
    __tablename__ = "risk_scores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False)
    
    # L1: Fast path results
    l1_rule_score = Column(Float)
    l1_rule_triggers = Column(Text)  # JSON list of triggered rules
    l1_lgbm_score = Column(Float)
    l1_lgbm_top_features = Column(Text)  # JSON: top contributing features
    l1_combined_score = Column(Float)
    l1_latency_ms = Column(Float)
    
    # L2: Deep path results
    l2_gnn_score = Column(Float)
    l2_gnn_attention_weights = Column(Text)  # JSON: node attention for explainability
    l2_ring_detected = Column(Boolean, default=False)
    l2_ring_id = Column(String(36))
    l2_ring_score = Column(Float)
    l2_latency_ms = Column(Float)
    
    # Combined AEGIS score
    aegis_score = Column(Float)  # Final combined risk score
    risk_level = Column(String(10))  # low, medium, high, critical
    recommended_action = Column(String(30))  # approve, step_up_auth, review, block
    
    # Causal explanation
    causal_explanation = Column(Text)  # JSON: causal factors + counterfactual
    causal_top_factors = Column(Text)  # JSON: top 5 causal risk drivers
    counterfactual = Column(Text)  # "If X were different, risk would be Y"
    
    # Chargeback prediction
    chargeback_probability = Column(Float)
    predicted_dispute_days = Column(Integer)  # Predicted days until chargeback
    
    scored_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="risk_scores")
    
    __table_args__ = (
        Index("idx_riskscore_txn", "transaction_id"),
        Index("idx_riskscore_aegis", "aegis_score"),
        Index("idx_riskscore_level", "risk_level"),
    )


class AttackSimulation(Base):
    """Recorded fraud attack injections for the live demo and dashboard."""
    __tablename__ = "attack_simulations"

    id = Column(String(36), primary_key=True)
    attack_type = Column(String(30), nullable=False)
    intensity = Column(String(10), nullable=False)
    transactions_injected = Column(Integer, nullable=False)
    detected_count = Column(Integer, nullable=False, default=0)
    detection_rate = Column(Float, default=0.0)
    avg_detection_latency_ms = Column(Float)
    rings_identified = Column(Integer, default=0)
    result_summary = Column(Text)  # JSON summary for replay in the dashboard
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_attack_created", "created_at"),
        Index("idx_attack_type", "attack_type"),
    )


class GraphEdge(Base):
    """Heterogeneous graph edges for GNN."""
    __tablename__ = "graph_edges"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    source_type = Column(String(20), nullable=False)  # user, device, ip, card, merchant, bank
    source_id = Column(String(64), nullable=False)
    target_type = Column(String(20), nullable=False)
    target_id = Column(String(64), nullable=False)
    edge_type = Column(String(30), nullable=False)  # MADE_TXN, USED_DEVICE, FROM_IP, PAID_WITH, SENT_TO
    
    # Edge attributes
    weight = Column(Float, default=1.0)
    transaction_id = Column(String(36))
    amount = Column(BigInteger)
    timestamp = Column(DateTime)
    
    __table_args__ = (
        Index("idx_edge_source", "source_type", "source_id"),
        Index("idx_edge_target", "target_type", "target_id"),
        Index("idx_edge_type", "edge_type"),
    )
