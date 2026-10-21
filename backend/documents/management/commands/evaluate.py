import json
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from documents.services.openai_client import chat_model, embed_texts, embedding_model
from documents.services.qa import (
    CANDIDATES_PER_METHOD,
    NOT_FOUND_MESSAGE,
    SEARCH_MODES,
    answer_question,
    is_relevant,
    rewrite_question,
    search_chunks,
)

DEFAULT_FILE = Path(settings.BASE_DIR) / "evaluation" / "questions.json"
RESULTS_DIR = Path(settings.BASE_DIR) / "evaluation" / "results"
RETRIEVE_K = 10  # look at the top 10 for MRR
ANSWER_K = 5  # the model sees the top 5
CITATION = re.compile(r"\[(\d+)\]")


def pct(values):
    values = list(values)
    return round(100 * sum(values) / len(values), 1) if values else None


def fmt(value, width=8):
    return f"{'-' if value is None else value:<{width}}"


def is_expected(chunk_or_source, expected):
    if isinstance(chunk_or_source, dict):
        return chunk_or_source["page"] in expected.get(chunk_or_source["document_id"], ())
    return chunk_or_source.page_number in expected.get(chunk_or_source.document_id, ())


def score_retrieval(results, case):
    expected = case["expected_pages"]
    top = results[:ANSWER_K]
    kept = [chunk for chunk in top if is_relevant(chunk)]
    preview = [
        f"{chunk.document.title[:20]} p{chunk.page_number} {chunk.match} {float(chunk.distance):.2f}"
        for chunk in top
    ]

    if not case["answerable"]:
        return {"rejected": not kept, "kept": len(kept), "top": preview}

    rank = next(
        (position for position, chunk in enumerate(results, start=1) if is_expected(chunk, expected)),
        None,
    )
    return {
        "rank": rank,
        "hit1": rank == 1,
        "hit5": rank is not None and rank <= ANSWER_K,
        "rr": 1 / rank if rank else 0.0,
        "kept_hit5": any(is_expected(chunk, expected) for chunk in kept),
        "top": preview,
    }


def score_answer(case, user, rewrite):
    result = answer_question(case["question"], user, history=case["history"], rewrite=rewrite)
    answer = result["answer"]
    refused = NOT_FOUND_MESSAGE.rstrip(".").lower() in answer.lower()

    cited_numbers = {int(n) for n in CITATION.findall(answer)}
    cited = [source for source in result["sources"] if source["number"] in cited_numbers]
    correct_citation = any(is_expected(source, case["expected_pages"]) for source in cited)

    passed = (not refused and correct_citation) if case["answerable"] else refused
    return {
        "refused": refused,
        "correct_citation": correct_citation,
        "passed": passed,
        "answer": answer,
    }


def summarize(rows, modes, with_answers):
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    summary = {
        "counts": {"answerable": len(answerable), "unanswerable": len(unanswerable)},
        "modes": {},
        "by_type": {},
    }

    for mode in modes:
        scored = [row["modes"][mode] for row in answerable]
        refused = [row["modes"][mode] for row in unanswerable]
        summary["modes"][mode] = {
            "hit@1": pct(s["hit1"] for s in scored),
            "hit@5": pct(s["hit5"] for s in scored),
            "mrr": round(sum(s["rr"] for s in scored) / len(scored), 3) if scored else None,
            "kept@5": pct(s["kept_hit5"] for s in scored),
            "rejected": pct(s["rejected"] for s in refused),
        }
        types = sorted({row["type"] for row in answerable})
        summary["by_type"][mode] = {
            t: pct(row["modes"][mode]["hit5"] for row in answerable if row["type"] == t)
            for t in types
        }

    if with_answers:
        summary["answers"] = {
            "answered_with_correct_citation": pct(row["answer"]["passed"] for row in answerable),
            "correctly_refused": pct(row["answer"]["passed"] for row in unanswerable),
        }
    return summary


class Command(BaseCommand):
    help = "Measure retrieval quality on a labeled question set."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True)
        parser.add_argument("--file", default=str(DEFAULT_FILE))
        parser.add_argument("--modes", nargs="+", choices=SEARCH_MODES, default=list(SEARCH_MODES))
        parser.add_argument("--candidates", type=int, default=CANDIDATES_PER_METHOD)
        parser.add_argument(
            "--no-rewrite", action="store_true",
            help="Search follow-ups with the original question instead of the rewritten one",
        )
        parser.add_argument(
            "--answers", action="store_true",
            help="Also generate full answers (default search mode). Uses more API calls.",
        )
        parser.add_argument("--only", nargs="+", help="Run only these case ids")
        parser.add_argument("--label", default="", help="Short name for this run")

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(f"No user named {options['user']!r}")

        cases = self.load_cases(Path(options["file"]), user)
        if options["only"]:
            cases = [case for case in cases if case["id"] in options["only"]]
            if not cases:
                raise CommandError("No cases matched --only")

        rewrite = not options["no_rewrite"]
        modes = options["modes"]
        rows = []

        self.stdout.write(f"Evaluating {len(cases)} cases...")
        for case in cases:
            self.stdout.write(f"  {case['id']}")
            search_query = (
                rewrite_question(case["question"], case["history"]) if rewrite else case["question"]
            )
            question_vector = embed_texts([search_query])[0]

            row = {
                "id": case["id"],
                "type": case["type"],
                "answerable": case["answerable"],
                "question": case["question"],
                "search_query": search_query,
                "modes": {},
            }
            for mode in modes:
                results = search_chunks(
                    search_query,
                    user,
                    top_k=RETRIEVE_K,
                    mode=mode,
                    question_vector=question_vector,
                    candidates=options["candidates"],
                )
                row["modes"][mode] = score_retrieval(results, case)

            if options["answers"]:
                row["answer"] = score_answer(case, user, rewrite)
            rows.append(row)

        summary = summarize(rows, modes, options["answers"])
        self.print_report(summary, rows, modes, options)
        self.save(summary, rows, options, rewrite)

    def load_cases(self, path, user):
        if not path.exists():
            raise CommandError(f"Question file not found: {path}")
        cases = json.loads(path.read_text(encoding="utf-8"))

        titles = {
            doc.title: doc.id
            for doc in Document.objects.filter(owner=user, status=Document.Status.READY)
        }
        seen_ids = set()
        for case in cases:
            if case["id"] in seen_ids:
                raise CommandError(f"Duplicate case id: {case['id']}")
            seen_ids.add(case["id"])

            case.setdefault("history", [])
            case.setdefault("type", "semantic")
            case["answerable"] = bool(case.get("expected"))

            expected = {}
            for item in case.get("expected", []):
                document_id = titles.get(item["document"])
                if document_id is None:
                    raise CommandError(
                        f"Case {case['id']!r}: no ready document titled {item['document']!r}.\n"
                        f"Your documents: {sorted(titles)}"
                    )
                expected.setdefault(document_id, set()).update(item["pages"])
            case["expected_pages"] = expected
        return cases

    def print_report(self, summary, rows, modes, options):
        counts = summary["counts"]
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nRESULTS  ({counts['answerable']} answerable, {counts['unanswerable']} unanswerable, "
            f"candidates={options['candidates']}, rewrite={'off' if options['no_rewrite'] else 'on'})"
        ))
        self.stdout.write(f"{'mode':<10}{'Hit@1':<8}{'Hit@5':<8}{'MRR':<8}{'Kept@5':<8}{'Rejected':<8}")
        for mode in modes:
            m = summary["modes"][mode]
            self.stdout.write(
                f"{mode:<10}{fmt(m['hit@1'])}{fmt(m['hit@5'])}{fmt(m['mrr'])}"
                f"{fmt(m['kept@5'])}{fmt(m['rejected'])}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("\nHIT@5 BY QUESTION TYPE"))
        types = sorted({t for by_mode in summary["by_type"].values() for t in by_mode})
        self.stdout.write(f"{'mode':<10}" + "".join(f"{t:<14}" for t in types))
        for mode in modes:
            by_type = summary["by_type"][mode]
            self.stdout.write(f"{mode:<10}" + "".join(fmt(by_type.get(t), 14) for t in types))

        if "answers" in summary:
            a = summary["answers"]
            self.stdout.write(self.style.MIGRATE_HEADING(f"\nFULL ANSWERS ({settings.SEARCH_MODE} search)"))
            self.stdout.write(f"Answered with a correct citation: {a['answered_with_correct_citation']}%")
            self.stdout.write(f"Correctly refused:                {a['correctly_refused']}%")

        # Show failures for the last mode listed (hybrid by default)
        mode = modes[-1]
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nFAILURES ({mode})"))
        failures = 0
        for row in rows:
            scored = row["modes"][mode]
            failed = (not scored["hit5"]) if row["answerable"] else (not scored["rejected"])
            if not failed:
                continue
            failures += 1
            reason = "correct page not in top 5" if row["answerable"] else "not rejected"
            self.stdout.write(self.style.WARNING(f"\n  {row['id']} ({row['type']}): {reason}"))
            self.stdout.write(f"    question: {row['question']}")
            if row["search_query"] != row["question"]:
                self.stdout.write(f"    searched: {row['search_query']}")
            if row["answerable"] and scored["rank"]:
                self.stdout.write(f"    correct page found at rank {scored['rank']}")
            for line in scored["top"]:
                self.stdout.write(f"      - {line}")
        if failures == 0:
            self.stdout.write("  none")

    def save(self, summary, rows, options, rewrite):
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        label = f"-{options['label']}" if options["label"] else ""
        path = RESULTS_DIR / f"{timestamp}{label}.json"
        path.write_text(
            json.dumps(
                {
                    "label": options["label"],
                    "settings": {
                        "modes": options["modes"],
                        "candidates": options["candidates"],
                        "rewrite": rewrite,
                        "answers": options["answers"],
                        "chat_model": chat_model(),
                        "embedding_model": embedding_model(),
                    },
                    "summary": summary,
                    "cases": rows,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.stdout.write(f"\nSaved results to {path}")
