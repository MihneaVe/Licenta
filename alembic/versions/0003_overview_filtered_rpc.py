"""feedbacks_overview_filtered RPC - filtered Overview KPIs

Captures the Postgres function Overview.jsx calls through supabase-js
(`.rpc('feedbacks_overview_filtered', …)`). It was created directly on
Supabase and never versioned, so a fresh database broke the Overview page.

Returns the same shape as the feedbacks_overview view but applies the
dashboard header's quarter multi-select and date range. NULL/empty
p_districts means all quarters; NULL dates are unbounded. SECURITY INVOKER
is fine: it reads the `feedbacks` view, which executes with its owner's
privileges and is the anon-approved surface.

Revision ID: 0003_overview_rpc
Revises: 0002_views_security
Create Date: 2026-06-09
"""
from alembic import op

revision = "0003_overview_rpc"
down_revision = "0002_views_security"
branch_labels = None
depends_on = None


UPGRADE_SQL = r"""
CREATE OR REPLACE FUNCTION public.feedbacks_overview_filtered(
    p_districts text[]      DEFAULT NULL,
    p_from      timestamptz DEFAULT NULL,
    p_to        timestamptz DEFAULT NULL
)
RETURNS TABLE(total integer, avg_score integer, alert_count integer, top_topics jsonb)
LANGUAGE sql
STABLE
SET search_path TO 'public'
AS $function$
  with f as (
    select sentiment_score, sentiment_label, topic
    from feedbacks
    where (p_districts is null or cardinality(p_districts) = 0 or location = any (p_districts))
      and (p_from is null or created_at >= p_from)
      and (p_to   is null or created_at <= p_to)
  )
  select
    (select count(*)::int from f)                                        as total,
    (select round(avg(sentiment_score))::int from f)                     as avg_score,
    (select count(*)::int from f where sentiment_label = 'Negative')     as alert_count,
    (select coalesce(jsonb_agg(t order by t.n desc), '[]'::jsonb)
       from (select topic as name, count(*)::int as n
             from f
             group by topic
             order by count(*) desc
             limit 5) t)                                                 as top_topics;
$function$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        GRANT EXECUTE ON FUNCTION public.feedbacks_overview_filtered(text[], timestamptz, timestamptz)
            TO anon, authenticated;
    END IF;
END $$;
"""

DOWNGRADE_SQL = r"""
DROP FUNCTION IF EXISTS public.feedbacks_overview_filtered(text[], timestamptz, timestamptz);
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
