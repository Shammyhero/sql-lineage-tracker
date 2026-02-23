-- =============================================
-- Cross-Pipeline Dashboard
-- DEPENDS ON: 01_user_activity + 02_finance
-- Does NOT depend on 03_inventory
-- =============================================

-- Combine user behavior with spending data
CREATE TABLE customer_360 AS
SELECT
    uj.user_id,
    uj.session_id,
    uj.session_start,
    uj.session_duration_min,
    uj.has_conversion,
    ms.category AS spending_category,
    ms.total_spent,
    ms.total_income,
    ms.txn_count
FROM user_journeys uj
LEFT JOIN monthly_spending ms ON uj.user_id = ms.account_id
    AND DATE_TRUNC('month', uj.session_start) = ms.month;

-- High-value customer segments
CREATE VIEW vip_customers AS
WITH customer_metrics AS (
    SELECT
        user_id,
        COUNT(DISTINCT session_id) AS total_sessions,
        SUM(CASE WHEN has_conversion THEN 1 ELSE 0 END) AS total_conversions,
        COALESCE(SUM(total_spent), 0) AS lifetime_spend,
        COALESCE(AVG(session_duration_min), 0) AS avg_session_min
    FROM customer_360
    GROUP BY user_id
)
SELECT
    user_id,
    total_sessions,
    total_conversions,
    lifetime_spend,
    avg_session_min,
    NTILE(5) OVER (ORDER BY lifetime_spend DESC) AS spend_quintile,
    CASE
        WHEN lifetime_spend > 10000 AND total_conversions > 10 THEN 'platinum'
        WHEN lifetime_spend > 5000 THEN 'gold'
        WHEN lifetime_spend > 1000 THEN 'silver'
        ELSE 'bronze'
    END AS tier
FROM customer_metrics;
