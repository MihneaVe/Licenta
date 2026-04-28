"""Bridge migration: expose ``analytics_socialpost`` to the React frontend.

The React app at ``Licenta/urban-sentiment/`` queries Supabase directly
for a ``feedbacks`` table with a flatter shape than Django's
``SocialPost``. Rather than duplicating data, we ship a Postgres view
that translates fields on the fly:

    Django field                      → feedbacks column
    -------------------------------------------------------
    id                                → id (text)
    author                            → author_name + author_initials
    source                            → color (reddit→amber, x→blue)
    district.name                     → location
    first associated TopicCategory    → topic
    content                           → content
    sentiment_label                   → sentiment_label
    (sentiment_score + 1) * 50        → sentiment_score (0..100)
    sentiment_score thresholds        → sentiment_color / sentiment_gradient
    COALESCE(original_date,
             scraped_at)              → created_at

The view is read-only — writes go through Django (``/ingest/`` paste form
or ``/api/ingest/`` POST). Real-time subscriptions on the React side
will quietly stop firing because Postgres ``LISTEN/NOTIFY`` doesn't
trigger on view changes; fall back to polling or the LiveFeed's pull
``fetchFeedbacks()`` on mount.

Idempotent — drops the view first if it already exists.
"""

from django.db import migrations


SQL_CREATE_VIEW = r"""
-- The React frontend originally created `feedbacks` as a real table
-- (urban-sentiment/supabase/schema.sql). Preserve any rows the user
-- manually inserted there by renaming it before we replace it with
-- our Django-backed view.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name   = 'feedbacks'
          AND table_type   = 'BASE TABLE'
    ) THEN
        EXECUTE 'ALTER TABLE public.feedbacks RENAME TO feedbacks_legacy';
    END IF;
END
$$;

DROP VIEW IF EXISTS public.feedbacks CASCADE;

CREATE OR REPLACE VIEW public.feedbacks AS
SELECT
    sp.id::text                                              AS id,
    sp.id                                                    AS post_id,
    COALESCE(NULLIF(sp.author, ''), 'anonymous')             AS author_name,
    COALESCE(
        NULLIF(UPPER(LEFT(sp.author, 2)), ''),
        'AN'
    )                                                        AS author_initials,
    CASE sp.source
        WHEN 'reddit' THEN 'amber'
        WHEN 'x'      THEN 'blue'
        WHEN 'facebook' THEN 'teal'
        WHEN 'google_maps' THEN 'green'
        ELSE 'slate'
    END                                                      AS color,
    COALESCE(d.name, 'București')                            AS location,
    COALESCE(
        (
            SELECT tc.name
            FROM analytics_socialpost_topics spt
            JOIN analytics_topiccategory tc ON tc.id = spt.topiccategory_id
            WHERE spt.socialpost_id = sp.id
            ORDER BY tc.id
            LIMIT 1
        ),
        'general'
    )                                                        AS topic,
    sp.content                                               AS content,
    COALESCE(NULLIF(sp.sentiment_label, ''), 'Neutral')      AS sentiment_label,
    -- Translate -1.0..+1.0 → 0..100. NULL sentiments default to 50 (neutral).
    GREATEST(0, LEAST(100,
        CASE
            WHEN sp.sentiment_score IS NULL THEN 50
            ELSE ROUND((sp.sentiment_score + 1) * 50)::int
        END
    ))                                                       AS sentiment_score,
    CASE
        WHEN sp.sentiment_score IS NULL                THEN 'text-slate-500'
        WHEN sp.sentiment_score >=  0.3                 THEN 'text-emerald-500'
        WHEN sp.sentiment_score <= -0.3                 THEN 'text-rose-500'
        ELSE                                                'text-amber-500'
    END                                                      AS sentiment_color,
    CASE
        WHEN sp.sentiment_score IS NULL                THEN 'from-slate-400 to-slate-600'
        WHEN sp.sentiment_score >=  0.3                 THEN 'from-emerald-400 to-emerald-600'
        WHEN sp.sentiment_score <= -0.3                 THEN 'from-rose-400 to-rose-600'
        ELSE                                                'from-amber-400 to-amber-600'
    END                                                      AS sentiment_gradient,
    COALESCE(sp.original_date, sp.scraped_at)                AS created_at,
    sp.source                                                AS source,
    sp.url                                                   AS url
FROM analytics_socialpost sp
LEFT JOIN analytics_district d ON d.id = sp.district_id
ORDER BY COALESCE(sp.original_date, sp.scraped_at) DESC;

-- Grant SELECT to Supabase's anon + authenticated roles so the
-- frontend's @supabase/supabase-js client can read it. We swallow
-- the error if those roles don't exist (e.g. local Postgres in dev
-- compose without Supabase auth).
DO $$
BEGIN
    BEGIN
        GRANT SELECT ON public.feedbacks TO anon;
    EXCEPTION WHEN undefined_object THEN
        NULL;
    END;
    BEGIN
        GRANT SELECT ON public.feedbacks TO authenticated;
    EXCEPTION WHEN undefined_object THEN
        NULL;
    END;
END
$$;
"""

SQL_DROP_VIEW = "DROP VIEW IF EXISTS public.feedbacks CASCADE;"


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0002_alter_district_options_district_centroid_lat_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_CREATE_VIEW,
            reverse_sql=SQL_DROP_VIEW,
        ),
    ]
