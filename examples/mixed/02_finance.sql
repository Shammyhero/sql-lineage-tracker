-- =============================================
-- Financial Transactions (independent pipeline)
-- Complex: MERGE, subqueries, HAVING, UNION ALL
-- =============================================

-- Deduplicate and clean raw transactions
CREATE TABLE clean_transactions AS
SELECT DISTINCT ON (txn_id)
    txn_id,
    account_id,
    txn_type,
    amount,
    currency,
    txn_date,
    merchant_name,
    COALESCE(category, 'uncategorized') AS category
FROM (
    SELECT * FROM bank_transactions
    UNION ALL
    SELECT * FROM credit_card_transactions
) all_txns
WHERE amount IS NOT NULL AND amount != 0
ORDER BY txn_id, txn_date DESC;

-- Monthly spending summary per account
CREATE VIEW monthly_spending AS
SELECT
    account_id,
    DATE_TRUNC('month', txn_date) AS month,
    category,
    SUM(CASE WHEN txn_type = 'debit' THEN amount ELSE 0 END) AS total_spent,
    SUM(CASE WHEN txn_type = 'credit' THEN amount ELSE 0 END) AS total_income,
    COUNT(*) AS txn_count,
    AVG(amount) AS avg_txn_amount
FROM clean_transactions
GROUP BY account_id, DATE_TRUNC('month', txn_date), category
HAVING COUNT(*) >= 2;

-- Fraud detection flags (reads from clean_transactions only)
CREATE TABLE fraud_flags AS
SELECT
    ct.txn_id,
    ct.account_id,
    ct.amount,
    ct.merchant_name,
    ct.txn_date,
    CASE
        WHEN ct.amount > (
            SELECT AVG(amount) * 5
            FROM clean_transactions sub
            WHERE sub.account_id = ct.account_id
        ) THEN 'high_amount'
        WHEN ct.merchant_name IN (
            SELECT merchant_name
            FROM clean_transactions
            GROUP BY merchant_name
            HAVING COUNT(DISTINCT account_id) <= 2
        ) THEN 'suspicious_merchant'
        ELSE 'normal'
    END AS flag_reason
FROM clean_transactions ct;
