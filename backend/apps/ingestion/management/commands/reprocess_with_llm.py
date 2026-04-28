"""Re-process stored SocialPost rows with the local Ollama LLM.

Cleans noisy paste content (author/date/title leaked into body),
generates a title where one is missing, and assigns each post to the
București district (or to the specific sector mentioned in the text).

Usage:
    python manage.py reprocess_with_llm
    python manage.py reprocess_with_llm --force            # redo even already-processed rows
    python manage.py reprocess_with_llm --ids 4 7 12       # only specific posts
    python manage.py reprocess_with_llm --limit 5          # cap for a smoke test
    python manage.py reprocess_with_llm --model qwen2.5:7b # override Ollama model
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.ingestion.llm_extractor import LLMExtractor
from apps.ingestion.reprocess import reprocess_all


class Command(BaseCommand):
    help = "Re-extract metadata + generate titles for stored posts using a local Ollama LLM."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-process rows that were already LLM-cleaned.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process at most N rows (useful for a smoke test).",
        )
        parser.add_argument(
            "--ids",
            type=int,
            nargs="+",
            default=None,
            help="Only re-process these SocialPost ids.",
        )
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help="Override the Ollama model name (default: qwen2.5:7b).",
        )

    def handle(self, *args, **opts):
        extractor = LLMExtractor(model=opts["model"]) if opts["model"] else LLMExtractor()

        self.stdout.write(
            f"Re-processing with model={extractor.model} "
            f"host={extractor.host}"
        )

        try:
            results = reprocess_all(
                extractor=extractor,
                force=opts["force"],
                limit=opts["limit"],
                only_ids=opts["ids"],
            )
        except RuntimeError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        changed = sum(1 for r in results if r.changed)
        skipped = sum(1 for r in results if r.skipped_reason)
        titled = sum(1 for r in results if r.title_generated)

        for r in results:
            if r.skipped_reason:
                self.stdout.write(
                    self.style.WARNING(f"  #{r.post_id} skipped: {r.skipped_reason}")
                )
                continue

            tag = self.style.SUCCESS("changed") if r.changed else self.style.NOTICE("noop")
            title = (r.fields.title or "")[:60]
            district = r.district_name or "—"
            gen = " (title generated)" if r.title_generated else ""
            self.stdout.write(
                f"  #{r.post_id} {tag} → district={district} title={title!r}{gen}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {len(results)} processed, {changed} updated, "
                f"{titled} titles generated, {skipped} skipped."
            )
        )
