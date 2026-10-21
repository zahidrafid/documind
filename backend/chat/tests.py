from unittest import mock

import openai
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from chat.models import ChatMessage, Conversation

User = get_user_model()

FAKE_RESULT = {
    "answer": "Late work loses ten percent per day [1].",
    "sources": [{
        "number": 1, "document_id": 1, "title": "Syllabus", "page": 2,
        "text": "Late work loses ten percent per day.", "distance": 0.4, "match": "both",
    }],
    "search_query": "What is the late policy?",
    "queries": ["What is the late policy?"],
}


class AskApiTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="test-pass-12345")
        self.bob = User.objects.create_user("bob", password="test-pass-12345")
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

        patcher = mock.patch("chat.views.answer_question", return_value=FAKE_RESULT)
        self.mock_answer = patcher.start()
        self.addCleanup(patcher.stop)

    def ask(self, question, conversation_id=None):
        return self.client.post(
            "/api/ask/",
            {"question": question, "conversation_id": conversation_id},
            format="json",
        )

    def test_first_question_creates_a_conversation(self):
        response = self.ask("What is the late policy?")

        self.assertEqual(response.status_code, 200)
        conversation = Conversation.objects.get(id=response.data["conversation"]["id"])
        self.assertEqual(conversation.owner, self.alice)
        self.assertEqual(conversation.title, "What is the late policy?")
        self.assertEqual(
            list(conversation.messages.values_list("role", flat=True)), ["user", "assistant"]
        )
        assistant = conversation.messages.get(role="assistant")
        self.assertEqual(assistant.sources, FAKE_RESULT["sources"])
        self.assertEqual(self.mock_answer.call_args.kwargs["history"], [])

    def test_follow_up_sends_recent_history(self):
        first = self.ask("What is the late policy?")
        conversation_id = first.data["conversation"]["id"]

        self.ask("Does that apply to the final?", conversation_id)

        self.assertEqual(
            self.mock_answer.call_args.kwargs["history"],
            [
                {"role": "user", "content": "What is the late policy?"},
                {"role": "assistant", "content": FAKE_RESULT["answer"]},
            ],
        )
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 4)

    def test_cannot_use_someone_elses_conversation(self):
        bobs = Conversation.objects.create(owner=self.bob, title="Bob's chat")

        response = self.ask("What is this about?", bobs.id)

        self.assertEqual(response.status_code, 404)
        self.mock_answer.assert_not_called()
        self.assertEqual(bobs.messages.count(), 0)

    def test_conversation_list_and_detail_are_private(self):
        Conversation.objects.create(owner=self.alice, title="Mine")
        bobs = Conversation.objects.create(owner=self.bob, title="Bob's chat")

        response = self.client.get("/api/conversations/")
        self.assertEqual([c["title"] for c in response.data], ["Mine"])
        self.assertEqual(self.client.get(f"/api/conversations/{bobs.id}/").status_code, 404)

    def test_nothing_is_saved_when_the_ai_service_fails(self):
        # OpenAIError is the base class the view catches for every OpenAI failure
        self.mock_answer.side_effect = openai.OpenAIError("connection failed")

        response = self.ask("What is the late policy?")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(ChatMessage.objects.count(), 0)
