-- ---------------------------------------------------------------------------
-- Exasol 7.1 note: CHECK constraints are not supported by the engine
-- (CREATE TABLE ... CHECK fails with "Feature not supported: constraint
-- check definition"). The former `CONSTRAINT ck_* CHECK (...)` clauses are
-- therefore omitted here and their rules are enforced in the application
-- layer instead:
--   inference.py  score/action ranges (score clamped to 0..100, action chosen
--                 from BLOCK/STEP_UP/MONITOR/ALLOW in one place)
--   backend.py    request validation for /score and /decision
-- Re-add them as CHECK clauses if the target engine supports the feature.
-- ---------------------------------------------------------------------------

-- ============================================================================
-- UPI Mule Fraud Detection — Exasol Schema
-- Matches SCHEMA.md exactly. Do not add columns without updating SCHEMA.md.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 2.1 upi_transactions
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE upi_transactions (
    txn_id              VARCHAR(40)     NOT NULL,
    txn_timestamp       TIMESTAMP       NOT NULL,
    sender_account      VARCHAR(20)     NOT NULL,
    receiver_account    VARCHAR(20)     NOT NULL,
    amount_inr          DECIMAL(14,2)   NOT NULL,
    sender_state        CHAR(2),
    receiver_state      CHAR(2),
    device_change_flag  BOOLEAN         DEFAULT FALSE NOT NULL,
    ip_risk_score       DECIMAL(4,3)    DEFAULT 0.000 NOT NULL,
    velocity_10min      INT             DEFAULT 0 NOT NULL,
    model_score         INT,
    action_taken        VARCHAR(10),
    ring_id             VARCHAR(20),
    model_version       VARCHAR(20),
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_upi_transactions PRIMARY KEY (txn_id)
)
;

-- ----------------------------------------------------------------------------
-- 2.2 decision_log  (append-only, immutable)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE decision_log (
    decision_id         DECIMAL(18,0)   NOT NULL,
    txn_id              VARCHAR(40)     NOT NULL,
    decision_timestamp  TIMESTAMP       NOT NULL,
    model_version       VARCHAR(20)     NOT NULL,
    score               INT             NOT NULL,
    threshold_block     INT             NOT NULL,
    threshold_stepup    INT             NOT NULL,
    action_taken        VARCHAR(10)     NOT NULL,
    explanation_json    VARCHAR(4000),
    feature_vector_json VARCHAR(4000),
    latency_ms          INT,
    exasol_fetch_ms     INT,
    gnn_inference_ms    INT,
    human_override      BOOLEAN         DEFAULT FALSE NOT NULL,
    override_by         VARCHAR(50),
    override_reason     VARCHAR(500),
    CONSTRAINT pk_decision_log PRIMARY KEY (decision_id),
    CONSTRAINT fk_decision_txn FOREIGN KEY (txn_id)
        REFERENCES upi_transactions (txn_id)

);

-- check IDENTITY is available before running:
--   SELECT * FROM EXA_SQL_KEYWORDS WHERE KEYWORD IN ('IDENTITY', 'PARTITION');
-- if not, use the sequence fallback below.

-- Optional sequence fallback if IDENTITY is unsupported:
-- CREATE OR REPLACE SEQUENCE seq_decision_id START WITH 1 INCREMENT BY 1;

-- ----------------------------------------------------------------------------
-- 2.3 threshold_governance
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE threshold_governance (
    version             VARCHAR(10)     NOT NULL,
    effective_date      TIMESTAMP       NOT NULL,
    set_by              VARCHAR(50)     NOT NULL,
    threshold_block     INT             NOT NULL,
    threshold_stepup    INT             NOT NULL,
    threshold_monitor   INT             NOT NULL,
    rationale           VARCHAR(500)    NOT NULL,
    CONSTRAINT pk_threshold_governance PRIMARY KEY (version)

);

-- ----------------------------------------------------------------------------
-- 2.4 ring_registry
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE ring_registry (
    ring_id             VARCHAR(20)     NOT NULL,
    first_detected      TIMESTAMP       NOT NULL,
    last_updated        TIMESTAMP       NOT NULL,
    account_count       INT             NOT NULL,
    total_volume_inr    DECIMAL(16,2)   NOT NULL,
    avg_score           DECIMAL(5,2)    NOT NULL,
    pattern_type        VARCHAR(30)     NOT NULL,
    status              VARCHAR(15)     DEFAULT 'active' NOT NULL,
    CONSTRAINT pk_ring_registry PRIMARY KEY (ring_id)

);

-- ----------------------------------------------------------------------------
-- 2.5 ring_members
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE ring_members (
    ring_id     VARCHAR(20)     NOT NULL,
    account_id  VARCHAR(20)     NOT NULL,
    joined_at   TIMESTAMP       NOT NULL,
    role        VARCHAR(15)     NOT NULL,
    CONSTRAINT pk_ring_members PRIMARY KEY (ring_id, account_id),
    CONSTRAINT fk_rm_ring FOREIGN KEY (ring_id)
        REFERENCES ring_registry (ring_id)

);

-- ----------------------------------------------------------------------------
-- 2.6 model_registry
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE model_registry (
    model_version   VARCHAR(20)     NOT NULL,
    trained_at      TIMESTAMP       NOT NULL,
    auc_pr          DECIMAL(5,4)    NOT NULL,
    auc_roc         DECIMAL(5,4)    NOT NULL,
    -- NULL when the training run did not record F1 (the UPI run does not).
    f1_score        DECIMAL(5,4),
    training_rows   DECIMAL(18,0)   NOT NULL,
    artifact_path   VARCHAR(200)    NOT NULL,
    is_active       BOOLEAN         DEFAULT FALSE NOT NULL,
    CONSTRAINT pk_model_registry PRIMARY KEY (model_version)

);

-- ----------------------------------------------------------------------------
-- 2.7 drift_metrics
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TABLE drift_metrics (
    metric_date   DATE            NOT NULL,
    feature_name  VARCHAR(40)     NOT NULL,
    psi_value     DECIMAL(5,4)    NOT NULL,
    status        VARCHAR(15)     NOT NULL,
    CONSTRAINT pk_drift_metrics PRIMARY KEY (metric_date, feature_name)

);

-- ============================================================================
-- Seed data — minimum viable rows so the app doesn't break on first query
-- ============================================================================

INSERT INTO threshold_governance
    (version, effective_date, set_by, threshold_block, threshold_stepup,
     threshold_monitor, rationale)
VALUES
    ('v3', '2026-04-10 09:00:00', 'r.sharma', 90, 70, 30, 'RBI circular update'),
    ('v2', '2026-03-28 09:00:00', 'r.sharma', 85, 65, 28, 'Tuning'),
    ('v1', '2026-03-15 09:00:00', 'system',   80, 60, 25, 'Initial');

INSERT INTO model_registry
    (model_version, trained_at, auc_pr, auc_roc, f1_score,
     training_rows, artifact_path, is_active)
VALUES
    ('TGAT+SAGE-v1.2', '2026-04-10 03:00:00', 0.8471, 0.9230, 0.8470,
     6362620, 'models/tgat_sage_v1.2.onnx', TRUE);

-- The UPI head is the served model (inference.load_model prefers it).
-- trained_at is the commit timestamp of c62b747, the run that produced
-- artifacts/upi_model_metrics.json; that JSON records metrics but no date.
-- f1_score is NULL: the training run does not persist F1.
INSERT INTO model_registry
    (model_version, trained_at, auc_pr, auc_roc, f1_score,
     training_rows, artifact_path, is_active)
VALUES
    ('upi-v1', '2026-10-15 22:08:37', 0.8704, 0.9813, NULL,
     80000, 'artifacts/upi_edge_model.onnx', TRUE);

-- Only one model may be active; demote the PaySim head now that the UPI head
-- is what /score loads whenever its artifact is present.
UPDATE model_registry SET is_active = FALSE
 WHERE model_version = 'TGAT+SAGE-v1.2';

INSERT INTO ring_registry
    (ring_id, first_detected, last_updated, account_count,
     total_volume_inr, avg_score, pattern_type, status)
VALUES
    ('RING-001', '2026-04-03 11:22:00', '2026-04-12 14:20:00', 8,
     1240000.00, 87.30, 'circular_flow', 'active'),
    ('RING-002', '2026-04-05 08:15:00', '2026-04-12 10:00:00', 5,
     620000.00,  82.10, 'layering',      'active'),
    ('RING-003', '2026-04-07 16:45:00', '2026-04-12 12:30:00', 12,
     2100000.00, 89.40, 'mixed',         'monitoring');
