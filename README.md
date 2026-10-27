# JaalNet: Real-Time UPI Mule-Fraud Detection with Exasol & Graph Neural Networks

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python: 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![Database: Exasol Personal](https://img.shields.io/badge/Database-Exasol%20Personal-002B49?logo=database)](https://www.exasol.com/)
[![Framework: FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Frontend: React + Vite](https://img.shields.io/badge/Frontend-React%20%2B%20Vite%20%2B%20Tailwind-61DAFB?logo=react&logoColor=black)](https://vitejs.dev/)
[![Tests: 201 Passed](https://img.shields.io/badge/Tests-201%20Passed-10B981?logo=pytest&logoColor=white)](tests/)

---

## 1. Problem Statement

India's Unified Payments Interface (UPI) handles over 14 billion transactions monthly, exceeding $250 billion in volume. While UPI enables instant peer-to-peer and merchant payments, its instantaneous settlement has become the primary exploit vector for **organized money mule syndicates, digital arrest scams, and cyber fraud rings**.

### Who Has the Problem?
* **Payment Service Provider (PSP) Banks & Remitter Banks** (e.g., SBI, HDFC, ICICI, Axis): Held liable under Reserve Bank of India (RBI) master directions for failing to intercept rapid mule outflows.
* **Fintech Payment Aggregators & TPAPs** (PhonePe, Google Pay, Paytm): Under strict regulatory compliance to detect synthetic accounts and account takeover without increasing transaction drop rates.
* **Indian Law Enforcement Agencies** (I4C, CFCFRMS, State Cyber Police): Face a multi-hour lag in tracing funds across smurfing chains, by which time funds are withdrawn at ATMs or routed through crypto ramps.
* **Everyday Indian Citizens**: Duped through social engineering and job scams into lending their bank accounts as unwitting money mules.

### Why It Matters
Traditional banking antifraud systems rely on single-transaction rule engines (e.g., amount thresholds, geographic location). Modern mule syndicates easily evade these rules by "smurfing"—splitting ₹25 Lakhs into 50 sub-threshold transfers of ₹40,000 across multiple hops within 45 seconds. By the time a victim dials the national 1930 cyber fraud helpline, the money has traversed 4 hops and exited the banking switch.

**JaalNet** addresses this challenge with sub-2 millisecond graph inference, in-database parallel graph clustering, and automated regulatory action.

---

## 2. Technical Architecture

```
                       [ Live UPI Transaction Stream ]
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EXASOL IN-MEMORY DATABASE GRID                         │
│  • 100,000+ Transaction Ledger (`UPI_TRANSACTIONS`)                         │
│  • 20,000 Graph Account Nodes (`UPI_ACCOUNTS`)                              │
│  • Thread-Safe Connection Pool with Dedicated Worker Channels               │
│  • In-Database Parallel Louvain UDF (`jaalnet_louvain_detector`)             │
│  • In-Memory 2-Hop Subgraph Traversal in < 1ms                              │
│  • Async Auditable Decision Logging (`DECISION_LOG`)                        │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   │ [Known in 20,000 Node Store?]       │
                   │ YES                                 │ NO (Cold Start)
                   ▼                                     ▼
┌──────────────────────────────────────┐  ┌───────────────────────────────────┐
│   TGAT + GraphSAGE Neural Network    │  │    CatBoost Cold-Start Model      │
│   • 32/64-dim in-memory embeddings   │  │    • Tabular Velocity & Device    │
│   • Multi-hop structural attention   │  │    • AUC-ROC: 0.9961              │
│   • Served via ONNX Runtime (<2ms)   │  │    • Zero-latency unseen account  │
└──────────────────┬───────────────────┘  └─────────────────┬─────────────────┘
                   │                                        │
                   └──────────────────┬─────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    JAALNET COMMAND CENTER & WAR ROOM                        │
│  • Real-Time Risk Reactor & Dynamic Cytoscape Subgraph Matrix               │
│  • 4D Temporal Velocity Scrubber (Instantaneous dV/dt Analysis)              │
│  • Exasol In-DB Cluster Community Detection Modal                           │
│  • Pre-Flight Merchant Shield Counterparty Evaluation                        │
│  • Autonomous AI Investigator Agent (Section 91 CrPC Lien & FIU-IND STR)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Innovations & Differentiators

1. **In-Database MPP Mule Cluster Discovery (Exasol Python 3 SET UDF)**:
   Instead of moving massive transaction graphs over networks to external graph tools, JaalNet registers a parallel Louvain community detector inside Exasol. It analyzes **100,000 transactions and identifies 52 distinct mule syndicates across 410 accounts in under 500ms**.

2. **Dual-Model Inference Pipeline with CatBoost Cold-Start Routing**:
   Over 40% of financial scams use newly opened accounts without historical graph embeddings. JaalNet routes established accounts through an ONNX-optimized **TGAT + GraphSAGE** network and newly discovered accounts through a specialized **CatBoost Cold-Start model** (AUC-ROC 0.9961), preventing blind spots.

3. **Autonomous AI Fraud Investigator ("War Room")**:
   An autonomous multi-step reasoning agent (`agent.py`) performs 5-phase triage: Telemetry Ingestion ➔ 2-Hop Graph Expansion ➔ Typology Classification (Circular Smurfing vs. Burst Fanout) ➔ Autonomous Lien Placement (`LIEN-RBI-...`) ➔ FIU-IND Suspicious Transaction Report (STR) compilation compliant with Section 12 PMLA 2002.

4. **Pre-Flight Merchant Shield**:
   An API endpoint (`/merchant/shield-check`) enabling e-commerce merchants and kirana stores to verify incoming counterparty VPAs before releasing goods, calculating 2-hop topological proximity to active mule rings.

5. **4D Temporal Velocity Scrubber & Cytoscape Halo Matrix**:
   An interactive timeline playback ($T+00:00$ to $T+03:00$) that models instantaneous cash velocity ($dV/dt$) and illuminates transaction waves with visual focus halos around target nodes and counterparties.

---

## 4. Repository Structure

```
├── agent.py                   # Autonomous AI investigator agent & FIU-IND reporter
├── backend.py                 # FastAPI backend server with /score & /rings endpoints
├── config.py                  # Global application configuration & thresholds
├── data.py                    # Transaction dataclasses & synthetic stream helpers
├── exasol_loader.py           # Thread-local connection pool & Exasol graph queries
├── inference.py               # ONNX Runtime & CatBoost inference pipeline
├── merchant_shield.py         # Pre-flight merchant counterparty risk evaluator
├── schema.sql                 # DDL definitions for Exasol tables & indexes
├── train_upi_model.py         # GraphSAGE + MLP edge classifier training pipeline
├── train_coldstart_model.py   # CatBoost cold-start tabular model training script
├── docker-compose.yml         # Container definitions for Exasol & services
├── Dockerfile.backend         # Python backend container definition
├── Dockerfile.frontend        # Production React web console container
├── requirements.txt           # Python package dependencies
├── requirements.lock          # Pinned dependency lockfile
├── pytest.ini                 # Pytest configuration
├── LICENSE                    # Apache 2.0 license
├── artifacts/                 # Serialized ONNX models, scalers, and node embeddings
├── frontend/                  # React + Vite + Tailwind CSS dashboard application
├── scripts/                   # Exasol initialization, UDF registration & load scripts
└── tests/                     # Unit, integration, and live Exasol test suite
```

---

## 5. Quickstart & Deployment Guide

### Prerequisites
* **Operating System:** Windows, Linux, or macOS
* **Python:** `3.11.x`
* **Node.js:** `v18.x` or higher (with `npm`)
* **Docker Desktop:** *(Required for Exasol Personal)*

---

### Step 1: Environment Setup

```bash
# Clone the repository
git clone https://github.com/shiveshkumar/JaalNet-UPI-Fraud-Defense.git
cd JaalNet-UPI-Fraud-Defense

# Create and activate Python virtual environment
# Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS:
# python3 -m venv .venv
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.lock
```

---

### Step 2: Launch & Seed Exasol Personal

```bash
# Run the official Exasol container
docker run -d --name exasol --privileged -p 8563:8563 \
  -e EXASOL_PASSWORD='YourSecurePassword123!' exasol/docker-db:7.1.30

# Initialize schema and load synthetic transactions
python scripts/_set_sys_password.py
python scripts/init_exasol.py
python scripts/load_synthetic_to_exasol.py

# Register in-database Louvain community detection Python 3 SET UDF
python scripts/init_louvain_udf.py
```

---

### Step 3: Start the Backend API

```bash
python -m uvicorn backend:app --host 127.0.0.1 --port 8000
```

* **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* **API Documentation (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Syndicate MPP Discovery:** [http://127.0.0.1:8000/syndicates/mpp-detect](http://127.0.0.1:8000/syndicates/mpp-detect)

---

### Step 4: Start the Frontend Console

In a separate terminal window:

```bash
cd frontend
npm install
npm run dev
```

* **Frontend Dashboard URL:** [http://localhost:5173/](http://localhost:5173/)

---

### Step 5: Run Automated Tests

Execute the automated test suite covering live Exasol connectivity, GNN inference, and decision logging:

```bash
pytest tests/ -v
```

---

## 6. API Reference

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/health` | `GET` | System health, model readiness, and memory telemetry |
| `/score` | `POST` | Real-time GNN / CatBoost transaction scoring with latency metrics |
| `/rings` | `GET` | List all discovered mule rings indexed in Exasol memory |
| `/rings/{ring_id}` | `GET` | Retrieve full graph topology (nodes and edges) for a specific ring |
| `/graph/neighborhood` | `GET` | 2-hop topological subgraph expansion for any target account |
| `/agent/investigate` | `POST` | Autonomous AI triage, debit freeze execution, and FIU-IND STR generation |
| `/merchant/shield-check` | `POST` | Pre-flight counterparty risk assessment for merchants |
| `/syndicates/mpp-detect` | `GET` | Trigger in-database parallel Louvain clustering across all transactions |

---

## 7. Compliance & Regulatory Standards

* **Reserve Bank of India (RBI):** Aligns with RBI master directions on digital payment fraud monitoring and real-time mule account freeze directives.
* **FIU-IND (Financial Intelligence Unit - India):** Generates standardized Suspicious Transaction Reports (STR) formatted for FINnet 2.0 electronic submission.
* **PMLA 2002 (Sec 12) & CrPC (Sec 91):** Formats autonomous lien attachments and evidence logs in compliance with statutory Indian criminal procedure rules.
* **I4C / CFCFRMS:** Typology classification matches Indian Cyber Crime Coordination Centre guidelines.

---

## 8. License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
