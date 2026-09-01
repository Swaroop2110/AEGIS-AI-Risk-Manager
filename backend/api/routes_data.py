"""AEGIS Data Generation API — Endpoints for synthetic data generation and management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class DataGenRequest(BaseModel):
    """Request to generate synthetic data."""
    num_customers: int = 10000
    num_merchants: int = 500
    num_transactions: int = 100000
    fraud_rate: float = 0.02
    seed: int = 42


class DataGenResponse(BaseModel):
    """Data generation result."""
    status: str
    customers_generated: int
    merchants_generated: int
    transactions_generated: int
    fraud_transactions: int
    graph_nodes: int
    graph_edges: int
    message: str


@router.post("/generate", response_model=DataGenResponse)
async def generate_synthetic_data(request: DataGenRequest):
    """Generate synthetic transaction data with fraud injection."""
    from data_engine.generate_all import generate_full_dataset
    
    try:
        result = generate_full_dataset(
            num_customers=request.num_customers,
            num_merchants=request.num_merchants,
            num_transactions=request.num_transactions,
            fraud_rate=request.fraud_rate,
            seed=request.seed,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    
    return DataGenResponse(**result)


@router.get("/stats")
async def get_data_stats():
    """Get statistics about generated data."""
    from database.connection import SessionLocal
    from database.models import Customer, Merchant, Transaction, Dispute
    
    db = SessionLocal()
    try:
        return {
            "customers": db.query(Customer).count(),
            "merchants": db.query(Merchant).count(),
            "transactions": db.query(Transaction).count(),
            "fraud_transactions": db.query(Transaction).filter(Transaction.is_fraud == True).count(),
            "disputes": db.query(Dispute).count(),
        }
    finally:
        db.close()
