-- =============================================
-- User Activity Tracking (standalone pipeline)
-- Complex: Window functions, CASE, self-join
-- =============================================

CREATE TABLE user_sessions AS
SELECT
    user_id,
    session_id,
    event_type,
    page_url,
    event_timestamp,
    LAG(event_timestamp) OVER (PARTITION BY user_id ORDER BY event_timestamp) AS prev_event_time,
    LEAD(page_url) OVER (PARTITION BY user_id ORDER BY event_timestamp) AS next_page,
    ROW_NUMBER() OVER (PARTITION BY user_id, session_id ORDER BY event_timestamp) AS event_order,
    CASE
        WHEN event_type = 'purchase' THEN 'conversion'
        WHEN event_type = 'add_to_cart' THEN 'engagement'
        WHEN event_type IN ('page_view', 'scroll') THEN 'browsing'
        ELSE 'other'
    END AS event_category
FROM clickstream_events
WHERE event_timestamp >= CURRENT_DATE - INTERVAL '90 days';

-- Sessionized user journeys (depends on user_sessions above)
CREATE TABLE user_journeys AS
WITH session_agg AS (
    SELECT
        user_id,
        session_id,
        MIN(event_timestamp) AS session_start,
        MAX(event_timestamp) AS session_end,
        COUNT(*) AS total_events,
        COUNT(CASE WHEN event_category = 'conversion' THEN 1 END) AS conversions,
        ARRAY_AGG(page_url ORDER BY event_order) AS page_path
    FROM user_sessions
    GROUP BY user_id, session_id
)
SELECT
    sa.*,
    EXTRACT(EPOCH FROM (sa.session_end - sa.session_start)) / 60.0 AS session_duration_min,
    CASE
        WHEN sa.conversions > 0 THEN true
        ELSE false
    END AS has_conversion
FROM session_agg sa;
