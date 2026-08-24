USER_BY_LOGIN = """
SELECT id, login, password_hash FROM users WHERE login = %(login)s
"""

USERS_COUNT = """
SELECT count(*) AS total FROM users
"""

SESSION_CREATE = """
INSERT INTO sessions (token, user_id, expires_at)
VALUES (%(token)s, %(user_id)s, now() + make_interval(secs => %(max_age)s))
"""

SESSION_USER = """
SELECT u.id, u.login
FROM sessions s
JOIN users u ON u.id = s.user_id
WHERE s.token = %(token)s AND s.expires_at > now()
"""

SESSION_DELETE = """
DELETE FROM sessions WHERE token = %(token)s
"""

SESSIONS_PURGE = """
DELETE FROM sessions WHERE expires_at <= now()
"""

CRITERIA_ALL = """
SELECT code, label, description, enabled, position FROM criteria ORDER BY position
"""

CALL_TYPES_ALL = """
SELECT code, label, description, enabled, position FROM call_types ORDER BY position
"""

CALL_JOIN = """
JOIN analyses a ON a.call_id = c.id
"""

CALL_WHERE = """
WHERE c.started_at >= %(since)s AND c.started_at < %(until)s
  AND a.call_type = ANY(%(types)s)
  AND (%(agent_id)s::bigint IS NULL OR c.agent_id = %(agent_id)s)
"""

CALL_SCORE_RATIO = """
JOIN LATERAL (
    SELECT avg(s.score)::float AS ratio
    FROM criterion_scores s WHERE s.call_id = c.id
) m ON TRUE
"""

CALL_SCORE_COUNTS = """
JOIN LATERAL (
    SELECT coalesce(sum(s.score), 0) AS met,
           count(*) AS total,
           avg(s.score)::float AS ratio
    FROM criterion_scores s WHERE s.call_id = c.id
) m ON TRUE
"""

CRITERIA_RATIOS = f"""
SELECT s.criterion_code AS code,
       avg(s.score)::float AS ratio,
       count(*) AS scored
FROM calls c
{CALL_JOIN}
JOIN criterion_scores s ON s.call_id = c.id
{CALL_WHERE}
GROUP BY s.criterion_code
"""

CRITERIA_DAILY_RATIOS = f"""
SELECT s.criterion_code AS code,
       (c.started_at AT TIME ZONE %(timezone)s)::date AS day,
       avg(s.score)::float AS ratio
FROM calls c
{CALL_JOIN}
JOIN criterion_scores s ON s.call_id = c.id
{CALL_WHERE}
GROUP BY s.criterion_code, day
ORDER BY day
"""

PERIOD_TOTALS = f"""
SELECT count(*) AS calls,
       coalesce(avg(m.ratio), 0)::float AS ratio
FROM calls c
{CALL_JOIN}
{CALL_SCORE_RATIO}
{CALL_WHERE}
"""

AGENT_TOTALS = """
SELECT c.agent_id,
       ag.display_name,
       count(*) AS calls,
       count(a.call_id) AS analyzed,
       avg(m.ratio)::float AS ratio,
       max(c.started_at) AS last_call
FROM calls c
JOIN agents ag ON ag.id = c.agent_id
LEFT JOIN analyses a ON a.call_id = c.id
LEFT JOIN LATERAL (
    SELECT avg(s.score)::float AS ratio
    FROM criterion_scores s WHERE s.call_id = c.id
) m ON TRUE
WHERE c.started_at >= %(since)s AND c.started_at < %(until)s
  AND (a.call_type IS NULL OR a.call_type = ANY(%(types)s))
  AND (%(agent_id)s::bigint IS NULL OR c.agent_id = %(agent_id)s)
GROUP BY c.agent_id, ag.display_name
"""

AGENT_DAILY_RATIOS = f"""
SELECT (c.started_at AT TIME ZONE %(timezone)s)::date AS day,
       avg(m.ratio)::float AS ratio
FROM calls c
{CALL_JOIN}
{CALL_SCORE_RATIO}
{CALL_WHERE}
GROUP BY day
ORDER BY day
"""

EXTREME_CALLS = f"""
WITH scored AS (
    SELECT c.id, c.started_at, m.met, m.total, m.ratio
    FROM calls c
    {CALL_JOIN}
    {CALL_SCORE_COUNTS}
    {CALL_WHERE}
      AND m.total > 0
)
(SELECT 'best' AS kind, * FROM scored ORDER BY ratio DESC, started_at DESC LIMIT 1)
UNION ALL
(SELECT 'worst' AS kind, * FROM scored ORDER BY ratio ASC, started_at DESC LIMIT 1)
"""

QUEUE_JOBS = """
SELECT j.call_id,
       j.status,
       j.attempts,
       j.error_code,
       j.updated_at,
       c.started_at,
       c.client_number,
       c.agent_id,
       ag.display_name AS agent_name
FROM processing_jobs j
JOIN calls c ON c.id = j.call_id
LEFT JOIN agents ag ON ag.id = c.agent_id
LEFT JOIN analyses a ON a.call_id = c.id
WHERE j.status = ANY(%(statuses)s)
  AND (a.call_type IS NULL OR a.call_type = ANY(%(types)s))
ORDER BY j.updated_at DESC
LIMIT %(limit)s
"""

QUEUE_COUNTS = """
SELECT status, count(*) AS total FROM processing_jobs GROUP BY status
"""

RECENT_ANALYSES = """
SELECT c.id,
       c.started_at,
       c.client_number,
       c.agent_id,
       ag.display_name AS agent_name,
       a.created_at,
       a.call_type,
       t.label AS call_type_label,
       m.met,
       m.total
FROM analyses a
JOIN calls c ON c.id = a.call_id
LEFT JOIN agents ag ON ag.id = c.agent_id
LEFT JOIN call_types t ON t.code = a.call_type
JOIN LATERAL (
    SELECT coalesce(sum(s.score), 0) AS met, count(*) AS total
    FROM criterion_scores s WHERE s.call_id = c.id
) m ON TRUE
WHERE a.call_type = ANY(%(types)s)
ORDER BY a.created_at DESC
LIMIT %(limit)s
"""

ANALYSES_TODAY = """
SELECT count(*) AS total
FROM analyses a
WHERE a.created_at >= %(since)s AND a.created_at < %(until)s
  AND a.call_type = ANY(%(types)s)
"""

CALLS_LIST_JOIN = """
FROM calls c
LEFT JOIN agents ag ON ag.id = c.agent_id
LEFT JOIN analyses a ON a.call_id = c.id
LEFT JOIN call_types t ON t.code = a.call_type
LEFT JOIN processing_jobs j ON j.call_id = c.id
"""

CALLS_LIST_WHERE = """
WHERE c.started_at >= %(since)s AND c.started_at < %(until)s
  AND (%(agent_id)s::bigint IS NULL OR c.agent_id = %(agent_id)s)
  AND (%(statuses)s::text[] IS NULL OR j.status = ANY(%(statuses)s))
  AND (
      a.call_type = ANY(%(types)s)
      OR (a.call_type IS NULL AND %(all_types)s)
  )
"""

CALLS_LIST = f"""
SELECT c.id,
       c.started_at,
       c.duration_seconds,
       c.client_number,
       c.agent_id,
       ag.display_name AS agent_name,
       a.call_type,
       t.label AS call_type_label,
       a.created_at AS analyzed_at,
       j.status,
       j.error_code,
       m.met,
       m.total
{CALLS_LIST_JOIN}
JOIN LATERAL (
    SELECT coalesce(sum(s.score), 0) AS met, count(*) AS total
    FROM criterion_scores s WHERE s.call_id = c.id
) m ON TRUE
{CALLS_LIST_WHERE}
ORDER BY c.started_at DESC
LIMIT %(limit)s OFFSET %(offset)s
"""

CALLS_LIST_COUNT = f"""
SELECT count(*) AS total
{CALLS_LIST_JOIN}
{CALLS_LIST_WHERE}
"""

AGENTS_WITH_CALLS = """
SELECT ag.id, ag.display_name
FROM agents ag
WHERE EXISTS (SELECT 1 FROM calls c WHERE c.agent_id = ag.id)
ORDER BY ag.display_name
"""

AGENT_BY_ID = """
SELECT id, external_id, display_name, email, profile_link FROM agents WHERE id = %(agent_id)s
"""

CALL_DETAILS = """
SELECT c.id,
       c.started_at,
       c.duration_seconds,
       c.direction,
       c.client_number,
       c.subject,
       c.crm_link,
       c.audio_path,
       c.agent_id,
       ag.display_name AS agent_name,
       a.call_type,
       t.label AS call_type_label,
       a.summary,
       a.strengths,
       a.weaknesses,
       a.recommendations,
       a.asr_model,
       a.analysis_model,
       a.prompt_label,
       a.processing_seconds,
       a.created_at AS analyzed_at,
       r.language,
       r.duration_ms,
       j.status,
       j.error_code
FROM calls c
LEFT JOIN agents ag ON ag.id = c.agent_id
LEFT JOIN analyses a ON a.call_id = c.id
LEFT JOIN call_types t ON t.code = a.call_type
LEFT JOIN asr_results r ON r.call_id = c.id
LEFT JOIN processing_jobs j ON j.call_id = c.id
WHERE c.id = %(call_id)s
"""

CALL_SCORES = """
SELECT s.criterion_code AS code,
       s.score,
       coalesce(cr.label, s.criterion_code) AS label,
       cr.description,
       cr.enabled,
       cr.position
FROM criterion_scores s
LEFT JOIN criteria cr ON cr.code = s.criterion_code
WHERE s.call_id = %(call_id)s
ORDER BY cr.position NULLS LAST, s.criterion_code
"""

CALL_SEGMENTS = """
SELECT raw -> 'segments' AS segments FROM asr_results WHERE call_id = %(call_id)s
"""
