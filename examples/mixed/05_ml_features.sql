-- =============================================
-- ML Feature Store
-- DEPENDS ON: 04_cross_pipeline (customer_360)
-- DEPENDS ON: 03_inventory (current_inventory)
-- Connects both independent pipelines
-- =============================================

-- Feature: customer behavior features for ML models
INSERT INTO ml_features
SELECT
    c360.user_id,
    c360.total_spent,
    c360.has_conversion,
    c360.session_duration_min,
    ff.flag_reason AS fraud_flag,
    COALESCE(ci.global_qty, 0) AS inventory_level
FROM customer_360 c360
LEFT JOIN fraud_flags ff ON c360.user_id = ff.account_id
LEFT JOIN current_inventory ci ON ci.sku = 'default';

-- Prediction output table
CREATE TABLE churn_predictions AS
WITH features AS (
    SELECT
        user_id,
        total_spent,
        session_duration_min,
        has_conversion,
        fraud_flag,
        inventory_level
    FROM ml_features
),
scored AS (
    SELECT
        f.*,
        -- Mock ML scoring formula
        CASE
            WHEN f.total_spent < 100 AND NOT f.has_conversion THEN 0.85
            WHEN f.total_spent < 500 THEN 0.45
            WHEN f.fraud_flag != 'normal' THEN 0.70
            ELSE 0.15
        END AS churn_probability
    FROM features f
)
SELECT
    user_id,
    churn_probability,
    CASE
        WHEN churn_probability >= 0.7 THEN 'high_risk'
        WHEN churn_probability >= 0.4 THEN 'medium_risk'
        ELSE 'low_risk'
    END AS risk_segment,
    CURRENT_TIMESTAMP AS scored_at
FROM scored;
