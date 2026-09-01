# AEGIS — Autonomous Evidence-Generating Intelligence System
## Razorpay AI Buildathon 2026 · Track 02: AI Risk Manager

> **Stop merchants losing money to fraud, returns, and chargebacks.**

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python main.py
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Dashboard at http://localhost:5173
```

### First Run Workflow
1. Open the dashboard → **Data Manager**
2. Click **Generate Dataset** (default: 1000 customers, 100 merchants, 10K transactions, 2% fraud)
3. Wait 30-60 seconds for generation to complete
4. Go to **Attack Simulator** → Click any attack type to see AEGIS detect fraud live
5. Go to **Dispute Defense** → Click **Defend** on any dispute to generate an evidence PDF
6. (Optional) Go to **Data Manager** → **Train LightGBM Model** for improved ML scoring
7. Go to **Metrics & ROI** to see precision/recall/F1 and ROI calculator

---

## 🏗️ Architecture

```
AEGIS
├── backend/               # Python FastAPI
│   ├── api/               # REST route handlers (5 routers + metrics)
│   ├── database/          # SQLAlchemy ORM + SQLite (8 tables)
│   ├── data_engine/       # Synthetic data generation + fraud injection
│   ├── intelligence/      # ML scoring pipeline (L1 + L2 + Causal AI)
│   ├── defense/           # 4-agent dispute representment
│   ├── config.py          # Central configuration
│   └── main.py            # FastAPI app entry point
└── frontend/              # React + Vite + Tailwind
    └── src/
        ├── pages/         # 6 dashboard pages
        │   ├── WarRoom.jsx          # Live transaction feed
        │   ├── GraphExplorer.jsx    # Cytoscape.js ring visualization
        │   ├── AttackSimulator.jsx  # Chaos engineering
        │   ├── DisputeCenter.jsx    # Auto-defense + PDF
        │   ├── MetricsDashboard.jsx # Precision/recall/ROI
        │   └── DataManager.jsx      # Data gen + model training
        ├── api.js          # Axios API client
        ├── utils.js        # Formatting utilities
        └── App.jsx         # Router + layout
```

---

## 🧠 Intelligence Core

### Dual-Engine Scoring Pipeline

```
Transaction → L1 Fast Path (<10ms)
              │   • Deterministic rules: velocity, z-score, geo, IP
              │   • LightGBM baseline (sigmoid fallback before training)
              │
              └─[score ≥ 0.5]→ L2 Deep Path (<50ms)
                                 • Graph ring detection via shared entities
                                 • Device/IP/card/VPA abuse pattern detection
                                 │
                                 └→ Causal AI Engine
                                     • Counterfactual explanations
                                     • "If X, risk drops from Y to Z"
```

### 5 Fraud Vectors Injected
| Vector | Pattern | Detection Method |
|---|---|---|
| Velocity Attack | 15-25 txns in 2min, 1 device | L1 velocity rule (≥10 → 0.65 weight) |
| Mule Ring | Layered fund transfers, shared VPA | L2 graph shared-entity detection |
| Friendly Fraud | Genuine purchase → dispute 45d later | Causal AI + chargeback predictor |
| Device Spoofing | 1 device, 10-20 identities | L2 graph (device shared by >5 users) |
| Account Takeover | Legit account, behavior shift | L1 new_device + geo_mismatch rules |

### 4-Agent Dispute Defense
```
Chargeback arrives →
  Agent 1: Evidence Aggregator  → pulls auth/device/delivery/behavioral vault
  Agent 2: Reason Code Strategist → maps Visa/MC/RuPay/UPI strategy
  Agent 3: Win Predictor         → probability + cost-benefit analysis
  Agent 4: PDF Compiler          → bank-ready evidence packet (ReportLab)
```

---

## 📊 API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/data/generate` | Generate synthetic dataset |
| `GET` | `/api/v1/data/stats` | Current DB record counts |
| `POST` | `/api/v1/scoring/score` | Score a transaction |
| `POST` | `/api/v1/scoring/train` | Train LightGBM L1 model |
| `POST` | `/api/v1/disputes/auto-defend` | Run 4-agent defense pipeline |
| `GET` | `/api/v1/disputes/list` | List all disputes |
| `POST` | `/api/v1/simulator/attack` | Launch a fraud attack |
| `GET` | `/api/v1/dashboard/stats` | Real-time KPIs |
| `GET` | `/api/v1/dashboard/graph/rings` | Detected fraud rings |
| `GET` | `/api/v1/dashboard/metrics/model` | Model evaluation metrics |
| `GET` | `/api/v1/metrics/evaluate` | Full precision/recall/F1 |
| `GET` | `/api/v1/metrics/ablation` | Layer-by-layer comparison |
| `GET` | `/api/v1/metrics/roi` | ROI calculator |
| `WS` | `/api/v1/dashboard/ws/stream` | Real-time transaction stream |

Full Swagger docs: http://localhost:8000/docs

---

## 🎯 Key Differentiators

1. **Causal AI** — "If delivery photo was collected, win probability jumps from 34% → 92%"
2. **Graph Ring Detection** — Real-time heterogeneous graph analysis catches rings tabular models miss
3. **Autonomous Defense** — 4-agent pipeline generates bank-compliant PDF in <3 seconds
4. **Evidence Vault** — Auth-time signals (3DS, device, IP, delivery) preserved for disputes 60 days later
5. **Attack Simulator** — Live chaos engineering demo for judges

---

## 📈 Performance Targets

| Metric | Target | Status |
|---|---|---|
| L1 Scoring Latency | < 10ms | ✅ Deterministic |
| L2 Graph Scoring | < 50ms | ✅ SQL-based |
| Evidence PDF Generation | < 3s | ✅ ReportLab |
| Fraud Detection Precision | > 85% | Train model first |
| Chargeback Win Rate | > 70% | Evidence completeness dependent |
| False Positive Rate | < 5% | Post-training |

---

## 🔧 Configuration

Edit `backend/config.py` to adjust:
- Fraud vector distribution (velocity/mule/friendly/spoofing/ATO percentages)
- Model thresholds (L1 fast threshold, high-risk threshold)
- Dispute defense thresholds (auto-defend, review, accept)
- LLM provider for evidence narratives (template/openai/gemini)
- Indian city distribution, MCC categories, payment method weights
