from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from documents.services.qa import (
    NOT_FOUND_MESSAGE,
    TOKEN_PATTERN,
    answer_question,
    build_queries,
    is_relevant,
    search_chunks,
)

from .helpers import FakeOpenAIMixin, TempMediaMixin, create_ready_document

User = get_user_model()

SEARCH_SETTINGS = {
    "SEARCH_MODE": "hybrid",
    "QUERY_STRATEGY": "none",
    "SEARCH_CANDIDATES": 20,
    "KEYWORD_WEIGHT": 1.0,
    "MAX_DISTANCE": 0.65,
    "KEYWORD_MAX_DISTANCE": 2.0,
}


class TokenPatternTests(SimpleTestCase):
    def test_keeps_emails_codes_and_rooms_whole(self):
        self.assertEqual(
            TOKEN_PATTERN.findall("email jlewis@collin.edu about ITSE-1359 in 111A?"),
            ["email", "jlewis@collin.edu", "about", "ITSE-1359", "in", "111A"],
        )


class RelevanceRuleTests(SimpleTestCase):
    def chunk(self, distance, match):
        return SimpleNamespace(distance=distance, match=match)

    def test_close_chunk_is_relevant(self):
        self.assertTrue(is_relevant(self.chunk(0.40, "vector"), 0.65, 0.80))

    def test_far_vector_only_chunk_is_not_relevant(self):
        self.assertFalse(is_relevant(self.chunk(0.70, "vector"), 0.65, 0.80))

    def test_far_keyword_match_uses_the_keyword_limit(self):
        self.assertTrue(is_relevant(self.chunk(0.72, "keyword"), 0.65, 0.80))
        self.assertFalse(is_relevant(self.chunk(0.85, "both"), 0.65, 0.80))


class QueryBuildingTests(FakeOpenAIMixin, SimpleTestCase):
    history = [
        {"role": "user", "content": "What is the late policy?"},
        {"role": "assistant", "content": "Ten percent per day."},
    ]

    def test_first_question_is_never_rewritten(self):
        queries, search_query = build_queries("Who is the instructor?", [], "both")
        self.assertEqual(queries, ["Who is the instructor?"])
        self.assertEqual(search_query, "Who is the instructor?")
        self.mock_chat.assert_not_called()

    def test_both_strategy_searches_original_and_rewritten(self):
        self.mock_chat.return_value = "Who is the instructor of the course with the late policy?"
        queries, search_query = build_queries("Who is the instructor?", self.history, "both")
        self.assertEqual(
            queries,
            ["Who is the instructor?", "Who is the instructor of the course with the late policy?"],
        )
        self.assertEqual(search_query, queries[1])

    def test_duplicate_phrasings_are_searched_once(self):
        self.mock_chat.return_value = "Who is the instructor?"
        queries, _ = build_queries("Who is the instructor?", self.history, "both")
        self.assertEqual(queries, ["Who is the instructor?"])


@override_settings(**SEARCH_SETTINGS)
class SearchTests(TempMediaMixin, FakeOpenAIMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.alice = User.objects.create_user("alice", password="test-pass-12345")
        self.bob = User.objects.create_user("bob", password="test-pass-12345")
        self.syllabus = create_ready_document(self.alice, "Syllabus", [
            "Instructor contact: jlewis@collin.edu and office IT Center 111A.",
            "Late work loses ten percent per day.",
        ])
        create_ready_document(self.bob, "Bob notes", ["Late work is never accepted in this class."])

    def test_search_never_returns_other_users_chunks(self):
        results = search_chunks("late work policy", self.alice, top_k=10)
        self.assertTrue(results)
        self.assertTrue(all(chunk.document.owner_id == self.alice.id for chunk in results))

    def test_document_filter_limits_the_search(self):
        other = create_ready_document(self.alice, "Lab rules", ["Late work rules for the lab."])
        results = search_chunks("late work", self.alice, top_k=10, document_ids=[other.id])
        self.assertEqual({chunk.document_id for chunk in results}, {other.id})

    def test_keyword_search_matches_a_whole_email_address(self):
        results = search_chunks("jlewis@collin.edu", self.alice, top_k=1, mode="keyword")
        self.assertEqual(results[0].page_number, 1)
        self.assertEqual(results[0].match, "keyword")

    def test_hybrid_ranks_chunk_found_by_both_methods_first(self):
        results = search_chunks("late work", self.alice, top_k=1)
        self.assertEqual(results[0].page_number, 2)
        self.assertEqual(results[0].match, "both")

    def test_unrelated_question_is_refused_without_calling_the_model(self):
        result = answer_question("capital of France", self.alice)
        self.assertEqual(result["answer"], NOT_FOUND_MESSAGE)
        self.assertEqual(result["sources"], [])
        self.mock_chat.assert_not_called()

    def test_answer_returns_sources_with_page_numbers(self):
        result = answer_question("What happens with late work?", self.alice)

        self.mock_chat.assert_called_once()
        self.assertEqual(result["answer"], self.chat_reply)
        self.assertEqual(result["sources"][0]["title"], "Syllabus")
        self.assertEqual(result["sources"][0]["page"], 2)
        prompt = self.mock_chat.call_args.args[1]
        self.assertIn("[1] Syllabus, page 2", prompt)
