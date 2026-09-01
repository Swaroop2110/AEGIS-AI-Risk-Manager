"""End-to-end synthetic dataset generation for the AEGIS Phase 1 backbone."""

from dataclasses import replace
from typing import Sequence

from config import DataGenerationConfig, data_config
from database.connection import SessionLocal, init_db

from .evidence_generator import generate_evidence_bulk
from .fraud_injector import inject_fraud
from .graph_builder import persist_transaction_graph
from .profiles import generate_customers, generate_merchants
from .transactions import generate_transactions


def _persist_evidence(db, transactions: Sequence, batch_size: int = 5_000) -> int:
    """Generate and write evidence records in bounded batches."""
    evidence_count = 0
    for start in range(0, len(transactions), batch_size):
        batch = transactions[start:start + batch_size]
        evidence = generate_evidence_bulk(batch)
        db.bulk_save_objects(evidence)
        db.commit()
        evidence_count += len(evidence)
    return evidence_count


def _build_generation_config(
    num_customers: int,
    num_merchants: int,
    num_transactions: int,
    fraud_rate: float,
    seed: int,
) -> tuple[DataGenerationConfig, int]:
    """Validate input and reserve the requested fraud share of the final dataset."""
    if num_customers < 1:
        raise ValueError("num_customers must be at least 1")
    if num_merchants < 1:
        raise ValueError("num_merchants must be at least 1")
    if num_transactions < 1:
        raise ValueError("num_transactions must be at least 1")
    if not 0.0 <= fraud_rate < 1.0:
        raise ValueError("fraud_rate must be between 0.0 (inclusive) and 1.0 (exclusive)")

    fraud_transactions = round(num_transactions * fraud_rate)
    legitimate_transactions = num_transactions - fraud_transactions
    if legitimate_transactions < 1:
        raise ValueError("num_transactions and fraud_rate must leave at least one legitimate transaction")

    return (
        replace(
            data_config,
            num_customers=num_customers,
            num_merchants=num_merchants,
            num_transactions=legitimate_transactions,
            fraud_rate=fraud_rate,
            seed=seed,
        ),
        fraud_transactions,
    )


def generate_full_dataset(
    num_customers: int = 10_000,
    num_merchants: int = 500,
    num_transactions: int = 100_000,
    fraud_rate: float = 0.02,
    seed: int = 42,
) -> dict:
    """Generate the Phase 1 dataset and persist transactions, evidence, and graph edges.

    ``num_transactions`` is the final requested total, rather than the number
    of legitimate records before fraud injection. This keeps the resulting
    fraud rate exact (subject to integer rounding) and makes the API response
    unambiguous.
    """
    config, fraud_target = _build_generation_config(
        num_customers,
        num_merchants,
        num_transactions,
        fraud_rate,
        seed,
    )

    init_db()
    db = SessionLocal()
    try:
        customers = generate_customers(db, config)
        merchants = generate_merchants(db, config)
        legitimate_transactions = generate_transactions(db, config, customers, merchants)

        fraud_result = inject_fraud(
            legitimate_transactions,
            customers,
            merchants,
            config=config,
            target_fraud_count=fraud_target,
        )
        injected_transactions = fraud_result["injected_transactions"]
        if injected_transactions:
            db.bulk_save_objects(injected_transactions)
            db.commit()

        disputes = fraud_result["disputes"]
        if disputes:
            db.bulk_save_objects(disputes)
            db.commit()

        all_transactions = fraud_result["transactions"]
        evidence_count = _persist_evidence(db, all_transactions)
        graph_stats = persist_transaction_graph(db, all_transactions)

        return {
            "status": "completed",
            "customers_generated": len(customers),
            "merchants_generated": len(merchants),
            "transactions_generated": len(all_transactions),
            "fraud_transactions": fraud_result["stats"]["total_fraud"],
            "graph_nodes": graph_stats["graph_nodes"],
            "graph_edges": graph_stats["graph_edges"],
            "message": (
                "Synthetic dataset generated with "
                f"{evidence_count} evidence records and {len(disputes)} disputes."
            ),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
