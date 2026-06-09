"""views + security — dashboard SQL views and RLS hardening

Captures the four read-only views the React dashboard consumes (previously
hand-applied on Supabase, so a fresh database built from migrations was
unusable by the frontend) and closes two security gaps:

* feedbacks            one row per post, dashboard-shaped (LiveFeed)
* feedbacks_overview   KPI aggregates (Overview)
* feedbacks_topics     per-topic mentions + average score (Topics)
* quarters_map         per-quarter sentiment + boundary geometry (Heatmap)

Security: rag_feedback / rag_postembedding (and alembic_version) had row level
security disabled while Supabase's default grants give the anon role full DML —
any holder of the publishable anon key could read or wipe them through
PostgREST. RLS is now enabled with no policies (deny-all): the backend talks to
Postgres as the table owner, which bypasses RLS, and the dashboard only reads
the views above, which execute with their owner's privileges.

The anon/authenticated grants are Supabase-specific; every statement touching
those roles is guarded so the migration also applies cleanly to a plain
Postgres (the docker-compose `localdb` profile) where they don't exist.

Revision ID: 0002_views_security
Revises: 0001_baseline
Create Date: 2026-06-09
"""
from alembic import op

revision = "0002_views_security"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


UPGRADE_SQL = r"""
-- ---------------------------------------------------------------------------
-- Views (CREATE OR REPLACE: safe on Supabase where they already exist)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW feedbacks AS
SELECT sp.id::text AS id,
       sp.id       AS post_id,
       COALESCE(NULLIF(sp.author, ''), 'anonymous')             AS author_name,
       COALESCE(NULLIF(UPPER(LEFT(sp.author, 2)), ''), 'AN')    AS author_initials,
       CASE sp.source
           WHEN 'reddit'      THEN 'amber'
           WHEN 'x'           THEN 'blue'
           WHEN 'facebook'    THEN 'teal'
           WHEN 'google_maps' THEN 'green'
           ELSE 'slate'
       END AS color,
       COALESCE(d.name, 'București') AS location,
       COALESCE((SELECT tc.name
                 FROM   analytics_socialpost_topics spt
                 JOIN   analytics_topiccategory tc ON tc.id = spt.topiccategory_id
                 WHERE  spt.socialpost_id = sp.id
                 ORDER  BY tc.id LIMIT 1), 'general') AS topic,
       sp.content,
       COALESCE(NULLIF(sp.sentiment_label, ''), 'Neutral') AS sentiment_label,
       GREATEST(0, LEAST(100, CASE
           WHEN sp.sentiment_score IS NULL THEN 50
           ELSE ROUND((sp.sentiment_score + 1) * 50)::int
       END)) AS sentiment_score,
       CASE
           WHEN sp.sentiment_score IS NULL   THEN 'text-slate-500'
           WHEN sp.sentiment_score >= 0.3    THEN 'text-emerald-500'
           WHEN sp.sentiment_score <= -0.3   THEN 'text-rose-500'
           ELSE 'text-amber-500'
       END AS sentiment_color,
       CASE
           WHEN sp.sentiment_score IS NULL   THEN 'from-slate-400 to-slate-600'
           WHEN sp.sentiment_score >= 0.3    THEN 'from-emerald-400 to-emerald-600'
           WHEN sp.sentiment_score <= -0.3   THEN 'from-rose-400 to-rose-600'
           ELSE 'from-amber-400 to-amber-600'
       END AS sentiment_gradient,
       COALESCE(sp.original_date, sp.scraped_at) AS created_at,
       sp.source,
       sp.url
FROM analytics_socialpost sp
LEFT JOIN analytics_district d ON d.id = sp.district_id
ORDER BY COALESCE(sp.original_date, sp.scraped_at) DESC;

CREATE OR REPLACE VIEW feedbacks_overview AS
SELECT (SELECT COUNT(*)::int FROM feedbacks)                       AS total,
       (SELECT ROUND(AVG(sentiment_score))::int FROM feedbacks)    AS avg_score,
       (SELECT COUNT(*)::int FROM feedbacks
        WHERE sentiment_label = 'Negative')                        AS alert_count,
       (SELECT COALESCE(JSONB_AGG(x.* ORDER BY x.n DESC), '[]'::jsonb)
        FROM (SELECT topic AS name, COUNT(*)::int AS n
              FROM feedbacks GROUP BY topic
              ORDER BY COUNT(*) DESC LIMIT 5) x)                   AS top_topics;

CREATE OR REPLACE VIEW feedbacks_topics AS
SELECT topic                          AS name,
       COUNT(*)::int                  AS mentions,
       ROUND(AVG(sentiment_score))::int AS avg_score
FROM feedbacks
WHERE topic IS NOT NULL AND topic <> 'general'
GROUP BY topic;

CREATE OR REPLACE VIEW quarters_map AS
SELECT d.id,
       d.name,
       p.name AS parent,
       COUNT(sp.id)::int AS post_count,
       ROUND(AVG(sp.sentiment_score)::numeric, 4)::float8 AS avg_sentiment,
       d.boundary_geojson,
       d.centroid_lat,
       d.centroid_lng
FROM analytics_district d
LEFT JOIN analytics_district p   ON p.id = d.parent_id
LEFT JOIN analytics_socialpost sp ON sp.district_id = d.id
WHERE d.kind = 'quarter'
  AND (d.boundary_geojson IS NOT NULL OR d.centroid_lat IS NOT NULL)
GROUP BY d.id, p.name;

-- ---------------------------------------------------------------------------
-- Row level security: deny-all for API roles on tables the dashboard must not
-- touch. The backend connects as the table owner and is unaffected.
-- ---------------------------------------------------------------------------

ALTER TABLE rag_feedback      ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_postembedding ENABLE ROW LEVEL SECURITY;
ALTER TABLE alembic_version   ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Supabase API-role grants: read-only on the views, nothing else. Guarded so
-- the migration also runs on plain Postgres without the Supabase roles.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON feedbacks, feedbacks_overview, feedbacks_topics, quarters_map
            FROM anon, authenticated;
        GRANT SELECT ON feedbacks, feedbacks_overview, feedbacks_topics, quarters_map
            TO anon, authenticated;
        REVOKE ALL ON rag_feedback, rag_postembedding, alembic_version
            FROM anon, authenticated;
    END IF;
END $$;
"""

DOWNGRADE_SQL = r"""
DROP VIEW IF EXISTS feedbacks_topics;
DROP VIEW IF EXISTS feedbacks_overview;
DROP VIEW IF EXISTS quarters_map;
DROP VIEW IF EXISTS feedbacks;

ALTER TABLE rag_feedback      DISABLE ROW LEVEL SECURITY;
ALTER TABLE rag_postembedding DISABLE ROW LEVEL SECURITY;
ALTER TABLE alembic_version   DISABLE ROW LEVEL SECURITY;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
