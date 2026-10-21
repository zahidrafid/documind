from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from documents.services.qa import SEARCH_MODES, search_chunks


class Command(BaseCommand):
    help = "Show vector, keyword and hybrid search results side by side."

    def add_arguments(self, parser):
        parser.add_argument("question")
        parser.add_argument("--user", required=True)
        parser.add_argument("--top-k", type=int, default=5)

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(f"No user named {options['user']!r}")

        self.stdout.write(f"\nQuestion: {options['question']}")
        for mode in SEARCH_MODES:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{mode.upper()}"))
            results = search_chunks(
                options["question"], user, top_k=options["top_k"], mode=mode
            )
            if not results:
                self.stdout.write("  (no results)")
            for position, chunk in enumerate(results, start=1):
                preview = chunk.text[:90].replace("\n", " ")
                self.stdout.write(
                    f"  {position}. page {chunk.page_number:<3} "
                    f"dist {float(chunk.distance):.3f}  [{chunk.match:<7}]  {preview}..."
                )
