from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from documents.services.qa import answer_question


class Command(BaseCommand):
    help = "Ask a question about a user's documents."

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

        result = answer_question(options["question"], user, top_k=options["top_k"])

        self.stdout.write("\nANSWER\n" + result["answer"] + "\n")
        if result["sources"]:
            self.stdout.write("SOURCES")
            for source in result["sources"]:
                preview = source["text"][:120].replace("\n", " ")
                self.stdout.write(
                    f"[{source['number']}] {source['title']}, page {source['page']} "
                    f"(distance {source['distance']}): {preview}..."
                )
