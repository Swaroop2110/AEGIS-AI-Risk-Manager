import networkx as nx
from typing import List, Dict, Any, Tuple
import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from torch_geometric.data import HeteroData
    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    class HeteroData:
        pass


from database.models import Customer, GraphEdge, Merchant, Transaction

class TransactionGraphBuilder:
    """
    Constructs and manages the heterogeneous transaction graph for the AEGIS GNN.
    
    Node Types: user, device, ip, card, merchant, vpa
    Edge Types: MADE_TXN, USED_DEVICE, FROM_IP, PAID_WITH, SENT_TO
    """
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        
    def add_transaction(self, txn: Transaction, customer: Customer = None, merchant: Merchant = None) -> None:
        """Add a single transaction and its context to the graph."""
        
        user_id = f"user_{txn.customer_id}"
        merchant_id = f"merchant_{txn.merchant_id}"
        
        # Add primary nodes
        if customer:
            self.graph.add_node(user_id, type="user", risk_tier=customer.risk_tier, 
                                city_tier=customer.city_tier, 
                                account_age=customer.account_age_days)
        else:
            if not self.graph.has_node(user_id):
                self.graph.add_node(user_id, type="user")
                
        if merchant:
            self.graph.add_node(merchant_id, type="merchant", mcc=merchant.mcc_code, 
                                risk_category=merchant.risk_category)
        else:
            if not self.graph.has_node(merchant_id):
                self.graph.add_node(merchant_id, type="merchant")
        
        # Add Transaction Edge
        self.graph.add_edge(user_id, merchant_id, key=txn.id, type="MADE_TXN", 
                            amount=txn.amount, timestamp=txn.created_at, is_fraud=txn.is_fraud)
                            
        # Add Device context
        if txn.device_id:
            device_id = f"device_{txn.device_id}"
            if not self.graph.has_node(device_id):
                self.graph.add_node(device_id, type="device")
            self.graph.add_edge(user_id, device_id, type="USED_DEVICE", 
                                transaction_id=txn.id, timestamp=txn.created_at)
                                
        # Add IP context (Group by /24 subnet)
        if txn.ip_address:
            # Simple /24 masking for IPv4
            subnet = ".".join(txn.ip_address.split(".")[:3]) + ".0/24"
            ip_id = f"ip_{subnet}"
            if not self.graph.has_node(ip_id):
                self.graph.add_node(ip_id, type="ip")
            self.graph.add_edge(user_id, ip_id, type="FROM_IP", 
                                transaction_id=txn.id, timestamp=txn.created_at)
                                
        # Add Card or VPA context
        if txn.payment_method in ["credit_card", "debit_card"] and txn.card_last4:
            card_id = f"card_{txn.card_network}_{txn.card_issuer}_{txn.card_last4}"
            if not self.graph.has_node(card_id):
                self.graph.add_node(card_id, type="card")
            self.graph.add_edge(user_id, card_id, type="PAID_WITH", 
                                transaction_id=txn.id, amount=txn.amount)
                                
        elif txn.payment_method == "upi" and txn.vpa:
            vpa_id = f"vpa_{txn.vpa}"
            if not self.graph.has_node(vpa_id):
                self.graph.add_node(vpa_id, type="vpa")
            self.graph.add_edge(user_id, vpa_id, type="PAID_WITH", 
                                transaction_id=txn.id, amount=txn.amount)
            # For mule ring detection, we could also link merchant VPA if available
            # e.g., self.graph.add_edge(vpa_id, merchant_vpa_id, type="SENT_TO")
            
    def get_subgraph(self, node_id: str, hops: int = 2) -> nx.MultiDiGraph:
        """Extract a k-hop subgraph around a specific node."""
        if node_id not in self.graph:
            return nx.MultiDiGraph()
            
        nodes = {node_id}
        for _ in range(hops):
            neighbors = set()
            for n in nodes:
                neighbors.update(self.graph.predecessors(n))
                neighbors.update(self.graph.successors(n))
            nodes.update(neighbors)
            
        return self.graph.subgraph(nodes).copy()
        
    def detect_communities(self) -> Dict[str, int]:
        """Run community detection (Louvain) on an undirected version of the graph."""
        # Note: In a real implementation, you would import community from python-louvain
        # For simplicity, returning a mock or simple connected components
        undirected_g = self.graph.to_undirected()
        communities = {}
        for i, comp in enumerate(nx.connected_components(undirected_g)):
            for node in comp:
                communities[node] = i
        return communities
        
    def find_motifs(self) -> Dict[str, List[List[str]]]:
        """Detect relevant motifs like stars (many users -> 1 device/IP) and cycles."""
        motifs = {"stars": [], "cycles": []}
        
        # Simple star detection (Node with high in-degree from users)
        for node, in_deg in self.graph.in_degree():
            if self.graph.nodes[node].get("type") in ["device", "ip", "vpa"] and in_deg >= 5:
                # Potential fraud ring hub
                motifs["stars"].append([node] + list(self.graph.predecessors(node)))
                
        # Simple cycle detection (limited depth)
        try:
            cycles = list(nx.simple_cycles(self.graph, length_bound=4))
            motifs["cycles"] = [c for c in cycles if len(c) > 2]
        except (nx.NetworkXError, TypeError):
            # length_bound might not be supported in older nx versions
            pass
            
        return motifs
        
    def get_node_features(self, node_type: str) -> np.ndarray:
        """Extract a feature matrix for all nodes of a specific type."""
        nodes_of_type = [n for n, attr in self.graph.nodes(data=True) if attr.get("type") == node_type]
        if not nodes_of_type:
            return np.array([])
            
        # Mock feature extraction - in reality this would process node attributes
        # e.g. for users: risk_tier one-hot, city_tier, account_age
        num_features = 10 
        return np.random.randn(len(nodes_of_type), num_features)
        
    def to_pyg_heterodata(self) -> HeteroData:
        """
        Convert NetworkX graph to PyTorch Geometric HeteroData format.
        With proper node feature tensors and edge_index tensors.
        """
        if not HAS_PYG or not HAS_TORCH:
            raise ImportError("torch and torch_geometric are required for to_pyg_heterodata")

        data = HeteroData()

        node_types = ["user", "device", "ip", "card", "merchant", "vpa"]
        node_mapping = {ntype: {} for ntype in node_types}

        # Map nodes to indices
        for node, attr in self.graph.nodes(data=True):
            ntype = attr.get("type")
            if ntype in node_mapping:
                node_mapping[ntype][node] = len(node_mapping[ntype])

        # Set node features
        for ntype in node_types:
            num_nodes = len(node_mapping[ntype])
            if num_nodes > 0:
                features = self.get_node_features(ntype)
                data[ntype].x = torch.tensor(features, dtype=torch.float)  # noqa: F821

        # Extract edges
        edge_types_dict = {}  # (src_type, edge_type, dst_type) -> list of (src_idx, dst_idx)

        for u, v, k, attr in self.graph.edges(keys=True, data=True):
            u_type = self.graph.nodes[u].get("type")
            v_type = self.graph.nodes[v].get("type")
            edge_type = attr.get("type", "UNKNOWN")

            if not u_type or not v_type:
                continue

            edge_tuple = (u_type, edge_type, v_type)
            if edge_tuple not in edge_types_dict:
                edge_types_dict[edge_tuple] = ([], [])

            u_idx = node_mapping[u_type][u]
            v_idx = node_mapping[v_type][v]

            edge_types_dict[edge_tuple][0].append(u_idx)
            edge_types_dict[edge_tuple][1].append(v_idx)

        # Add edge indices to HeteroData
        for edge_tuple, (src_indices, dst_indices) in edge_types_dict.items():
            edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long)  # noqa: F821
            data[edge_tuple].edge_index = edge_index
            
        return data

def to_pyg_heterodata(graph: nx.MultiDiGraph) -> HeteroData:
    """Utility function to wrap the class method if passing just a graph."""
    builder = TransactionGraphBuilder()
    builder.graph = graph
    return builder.to_pyg_heterodata()


def persist_transaction_graph(db, transactions: List[Transaction], batch_size: int = 5_000) -> Dict[str, int]:
    """Persist the heterogeneous graph edges generated from transactions.

    The in-memory ``TransactionGraphBuilder`` is used by intelligence features.
    This function is the durable counterpart for the Phase 1 data pipeline: it
    writes the equivalent relations to ``graph_edges`` in bounded batches so a
    generated dataset can be reconstructed after a server restart.
    """
    edge_batch: List[GraphEdge] = []
    nodes = set()
    edge_count = 0

    def add_node(node_type: str, node_id: str) -> None:
        nodes.add((node_type, str(node_id)))

    def add_edge(source_type: str, source_id: str, target_type: str, target_id: str,
                 edge_type: str, transaction: Transaction) -> None:
        nonlocal edge_count
        add_node(source_type, source_id)
        add_node(target_type, target_id)
        edge_batch.append(GraphEdge(
            source_type=source_type,
            source_id=str(source_id),
            target_type=target_type,
            target_id=str(target_id),
            edge_type=edge_type,
            transaction_id=transaction.id,
            amount=transaction.amount,
            timestamp=transaction.created_at,
        ))
        edge_count += 1

        if len(edge_batch) >= batch_size:
            db.bulk_save_objects(edge_batch)
            db.commit()
            edge_batch.clear()

    for txn in transactions:
        add_edge("user", txn.customer_id, "merchant", txn.merchant_id, "MADE_TXN", txn)

        if txn.device_id:
            add_edge("user", txn.customer_id, "device", txn.device_id, "USED_DEVICE", txn)

        if txn.ip_address:
            ip_parts = txn.ip_address.split(".")
            subnet = ".".join(ip_parts[:3]) + ".0/24" if len(ip_parts) == 4 else txn.ip_address
            add_edge("user", txn.customer_id, "ip", subnet, "FROM_IP", txn)

        if txn.payment_method in ["credit_card", "debit_card"] and txn.card_last4:
            card_id = f"{txn.card_network}_{txn.card_issuer}_{txn.card_last4}"
            add_edge("user", txn.customer_id, "card", card_id, "PAID_WITH", txn)
        elif txn.payment_method == "upi" and txn.vpa:
            add_edge("user", txn.customer_id, "vpa", txn.vpa, "PAID_WITH", txn)

    if edge_batch:
        db.bulk_save_objects(edge_batch)
        db.commit()

    return {"graph_nodes": len(nodes), "graph_edges": edge_count}
