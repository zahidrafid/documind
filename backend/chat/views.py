import logging

import openai
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from documents.services.qa import answer_question

from .models import ChatMessage, Conversation
from .serializers import (
    AskSerializer,
    ChatMessageSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
)

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 6  # last 3 questions and answers


def make_title(question, max_length=60):
    title = " ".join(question.split())
    return title if len(title) <= max_length else title[: max_length - 1] + "…"


class ConversationViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "delete", "head", "options"]

    def get_queryset(self):
        conversations = Conversation.objects.filter(owner=self.request.user)
        if self.action == "retrieve":
            conversations = conversations.prefetch_related("messages")
        return conversations

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ConversationDetailSerializer
        return ConversationSerializer


class AskView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ask"

    def post(self, request):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conversation = None
        history = []
        if data.get("conversation_id"):
            # 404 if it doesn't exist OR belongs to someone else
            conversation = get_object_or_404(
                Conversation, id=data["conversation_id"], owner=request.user
            )
            recent = list(
                conversation.messages.order_by("-created_at", "-id")[:HISTORY_MESSAGES]
            )
            history = [
                {"role": message.role, "content": message.content}
                for message in reversed(recent)
            ]

        try:
            result = answer_question(
                data["question"],
                request.user,
                history=history,
                top_k=data["top_k"],
                document_ids=data.get("document_ids"),
            )
        except openai.OpenAIError:
            logger.exception("OpenAI request failed")
            return Response(
                {"detail": "The AI service is unavailable right now. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Save the question and answer together, or not at all
        with transaction.atomic():
            if conversation is None:
                conversation = Conversation.objects.create(
                    owner=request.user, title=make_title(data["question"])
                )
            ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.Role.USER,
                content=data["question"],
            )
            assistant_message = ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.Role.ASSISTANT,
                content=result["answer"],
                sources=result["sources"],
                search_query=result["search_query"],
            )
            conversation.save(update_fields=["updated_at"])  # move it to the top

        return Response(
            {
                "conversation": ConversationSerializer(conversation).data,
                "message": ChatMessageSerializer(assistant_message).data,
            }
        )
