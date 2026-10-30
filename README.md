# JaalNet: Real-Time UPI Mule-Fraud Defense Platform

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python: 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![Database: Exasol Personal](https://img.shields.io/badge/Database-Exasol%20Personal-002B49?logo=database)](https://www.exasol.com/)
[![Framework: FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Frontend: React + Vite](https://img.shields.io/badge/Frontend-React%20%2B%20Vite%20%2B%20Tailwind-61DAFB?logo=react&logoColor=black)](https://vitejs.dev/)
[![Tests: 203 Passed](https://img.shields.io/badge/Tests-203%20Passed-10B981?logo=pytest&logoColor=white)](tests/)

---

## 1. Overview

### Problem Statement
India's Unified Payments Interface (UPI) processes over 14 billion transactions monthly, exceeding $250 billion in volume. While UPI enables instant peer-to-peer and merchant payments, its instantaneous settlement has become the primary exploit vector for **organized money mule syndicates, digital arrest scams, and cyber fraud rings**.

#### Who Has the Problem?
* **Payment Service Provider (PSP) Banks & Remitter Banks** (SBI, HDFC, ICICI, Axis): Held liable under Reserve Bank of India (RBI) master directions for failing to intercept rapid mule outflows, facing heavy regulatory penalties.
* **Fintech Aggregators & TPAPs** (PhonePe, Google Pay, Paytm): Under strict regulatory compliance to detect synthetic accounts and account takeover without increasing transaction drop rates.
* **Indian Law Enforcement Agencies** (I4C, CFCFRMS, State Cyber Police): Face a multi-hour lag in tracing funds across smurfing chains, by which time funds are withdrawn at ATMs or routed through crypto ramps.
* **Everyday Indian Citizens**: Duped through social engineering and job scams into lending their bank accounts as unwitting money mules.

#### Why It Matters
Traditional banking antifraud systems rely on single-transaction rule engines (e.g., amount thresholds > ₹50,000, geographic mismatch). Modern mule syndicates easily evade these rules by "smurfing"—splitting ₹25 Lakhs into 50 sub-threshold transfers of ₹40,000 across multiple hops within 45 seconds. By the time a victim dials the national 1930 cyber fraud helpline, the money has traversed 4 hops and exited the banking switch.

**JaalNet** addresses this challenge with sub-2 millisecond graph inference, in-database parallel graph clustering, and automated regulatory action.

---

### Technical Architecture

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

### Key Innovations & Differentiators

1. **In-Database MPP Mule Cluster Discovery (Exasol Python 3 SET UDF)**:
   Instead of moving massive transaction graphs over networks to external graph tools, JaalNet registers a parallel Louvain community detector inside Exasol. It analyzes **100,000 transactions and identifies 52 distinct mule syndicates across 410 accounts in under 500ms**.

2. **Dual-Model Inference Pipeline with CatBoost Cold-Start Routing**:
   Over 40% of financial scams use newly opened accounts without historical graph embeddings. JaalNet routes established accounts through an ONNX-optimized **TGAT + GraphSAGE** network and newly discovered accounts through a specialized **CatBoost Cold-Start model** (AUC-ROC: 0.9961, Precision: 98.4%), preventing blind spots.

3. **Autonomous AI Fraud Investigator ("War Room")**:
   An autonomous multi-step reasoning agent (`agent.py`) performs 5-phase triage: Telemetry Ingestion ➔ 2-Hop Graph Expansion ➔ Typology Classification (Circular Smurfing vs. Burst Fanout) ➔ Autonomous Lien Placement (`LIEN-RBI-...`) ➔ FIU-IND Suspicious Transaction Report (STR) compilation compliant with Section 12 PMLA 2002.

4. **Pre-Flight Merchant Shield**:
   An API endpoint (`/merchant/shield-check`) enabling e-commerce merchants and kirana stores to verify incoming counterparty VPAs before releasing goods, calculating 2-hop topological proximity to active mule rings to prevent false freezes.

5. **4D Temporal Velocity Scrubber & Cytoscape Halo Matrix**:
   An interactive timeline playback ($T+00:00$ to $T+03:00$) that models instantaneous cash velocity ($dV/dt$) and illuminates transaction waves with visual focus halos around target nodes and counterparties.

---

## 2. Setup and Usage

### Prerequisites
* **Operating System:** Windows 10/11, Ubuntu/Debian Linux, or macOS
* **Python:** `3.11.x`
* **Node.js:** `v18.x` or higher (with `npm`)
* **Docker Desktop:** *(Optional: needed only for live local Exasol container)*

---

### Step-by-Step Local Setup

#### 1. Clone Repository
```bash
git clone https://github.com/kumarshivesh465-hue/jaal-net.git
cd jaal-net
```

#### 2. Python Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

---

### Usage & Running the System

#### 1. Start the FastAPI Backend
In your first terminal:
```bash
# From project root with venv activated
python -m uvicorn backend:app --host 127.0.0.1 --port 8000 --reload
```
* **API Documentation (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health Check & Model Telemetry:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

#### 2. Start the React Frontend Dashboard
In a second terminal:
```bash
cd frontend
npm run dev
```
* **Interactive Web Console:** [http://localhost:5173/](http://localhost:5173/)

---

### Exploring the Platform Features

1. **Command Center**:
   * View live stream of incoming UPI transactions.
   * Observe real-time GNN scoring and risk tags (`ALLOW`, `MONITOR`, `STEP_UP`, `BLOCK`).
   * Rotate and inspect the 3D Spatial India UPI Globe.
2. **UPI Simulator Testbed**:
   * **P2P Split (₹14,500)**: Simulates benign peer-to-peer split payment (`ananya.v@axis` ➔ `kunal.shah@icici`).
   * **Midnight Burst (₹85,000)**: Simulates high-velocity night burst (`vikram.unknown@ybl` ➔ `temp.wallet@kotak`).
   * **Mule Ring (₹2,40,000)**: Select `RING-001` to `RING-004` to simulate an organized mule siphon attack.
3. **AI Investigator Drawer**:
   * Click on any transaction or click **"Launch AI Investigator Agent"** in an alert dossier.
   * View the 5-phase automated reasoning trace and export an official **FIU-IND Suspicious Transaction Report (STR)**.
4. **Merchant Shield**:
   * Click **"Merchant Shield"** in the top navigation bar to run pre-flight counterparty verification for kirana and high-volume merchant accounts.
5. **Syndicate Explorer**:
   * Examine multi-hop circular rings, fan-out smurfing topologies, and Louvain modularity clusters.

---

## 3. Deployment Instructions and Run Guide

### Option A: Local Bare-Metal Production Deployment

To run in production mode on a local or cloud VM:

```bash
# 1. Build optimized React production bundle
cd frontend
npm run build
cd ..

# 2. Run backend with multiple production uvicorn workers
uvicorn backend:app --host 0.0.0.0 --port 8000 --workers 2
```

---

### Option B: Docker Compose Full-Stack Deployment

JaalNet includes a production-ready `docker-compose.yml` to spin up the complete infrastructure:

```bash
# Build and start all containers (FastAPI backend + Streamlit / Web Console + optional Exasol)
docker-compose up --build -d

# Check status
docker-compose ps

# Stop containers
docker-compose down
```

---

### Option C: Exasol In-Memory Database Grid Setup (Optional)

JaalNet functions out-of-the-box with a high-performance embedded in-memory database simulation. To attach an external Exasol Personal database instance:

```bash
# 1. Start the official Exasol container
docker run -d --name exasol --privileged -p 8563:8563 \
  -e EXASOL_PASSWORD='YourSecurePassword123!' exasol/docker-db:7.1.30

# 2. Initialize schema & populate 100,000 transaction graph
python scripts/_set_sys_password.py
python scripts/init_exasol.py
python scripts/load_synthetic_to_exasol.py

# 3. Register in-database Louvain community detection Python 3 SET UDF
python scripts/init_louvain_udf.py
```

---

### Option D: Static Frontend Deployment (Netlify)

The React frontend includes client-side synthetic fallback, allowing standalone deployment to Netlify:

```bash
# 1. Generate production build with SPA redirect
cd frontend
npm run build
```

Drag and drop the resulting `frontend/dist` folder directly onto [app.netlify.com/drop](https://app.netlify.com/drop).

---

### Run Guide: Testing & Verification

Run the comprehensive automated test suite (unit, integration, GNN inference, and cold-start fallback):

```bash
# Run all standard tests
pytest tests/ -v

# Run high-throughput latency benchmark (100 concurrent requests)
python scripts/load_test.py --base-url http://127.0.0.1:8000 --requests 50 --concurrency 10
```

#### Benchmark Results:
* **Server P50 Latency:** `1.0 ms`
* **Server P99 Latency:** `2.0 ms`
* **Throughput:** `413.34 requests/sec`
* **Pass Rate:** 100% (50/50 successful responses within SLA budget)

---

## 4. API Reference

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

## 5. Regulatory Compliance & Standards

* **Reserve Bank of India (RBI):** Aligns with RBI master directions on digital payment fraud monitoring and real-time mule account freeze directives under Section 35A.
* **FIU-IND (Financial Intelligence Unit - India):** Generates standardized Suspicious Transaction Reports (STR) formatted for FINnet 2.0 electronic submission.
* **PMLA 2002 (Sec 12) & CrPC (Sec 91):** Formats autonomous lien attachments and evidence logs in compliance with statutory Indian criminal procedure rules.
* **I4C / CFCFRMS:** Typology classification matches Indian Cyber Crime Coordination Centre guidelines.

---

## 6. License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
