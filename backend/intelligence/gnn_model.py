"""Trainable heterogeneous GNN definition for the Phase 2 graph path."""

from __future__ import annotations

try:
    import torch
    from torch import nn
    from torch_geometric.nn import HeteroConv, SAGEConv

    HAS_PYG = True
except ImportError:
    HAS_PYG = False


if HAS_PYG:
    class HeteroFraudGNN(nn.Module):
        """Relation-aware GraphSAGE encoder with a transaction-risk head."""

        def __init__(self, metadata, hidden_channels: int = 128, num_layers: int = 3, dropout: float = 0.3):
            super().__init__()
            node_types, edge_types = metadata
            self.convs = nn.ModuleList()
            for _ in range(num_layers):
                self.convs.append(HeteroConv({
                    edge_type: SAGEConv((-1, -1), hidden_channels)
                    for edge_type in edge_types
                }, aggr="sum"))
            self.dropout = nn.Dropout(dropout)
            self.risk_head = nn.Sequential(
                nn.LazyLinear(hidden_channels),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_channels, 1),
            )

        def forward(self, x_dict, edge_index_dict):
            for conv in self.convs:
                x_dict = {
                    node_type: self.dropout(x.relu())
                    for node_type, x in conv(x_dict, edge_index_dict).items()
                }
            return {node_type: self.risk_head(x).squeeze(-1) for node_type, x in x_dict.items()}
else:
    class HeteroFraudGNN:  # pragma: no cover - only exercised without optional ML packages
        """Clear import-time fallback when PyTorch Geometric is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError("torch and torch-geometric are required to train HeteroFraudGNN")
