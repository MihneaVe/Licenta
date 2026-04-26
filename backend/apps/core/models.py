# Core no longer owns its own `Mood` model — the canonical store for
# civic posts is `apps.analytics.SocialPost`, populated by either the
# scrapers or the manual ingestion module (`apps.ingestion`).
