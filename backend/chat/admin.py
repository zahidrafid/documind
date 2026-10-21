from django.contrib import admin

from .models import ChatMessage, Conversation


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    fields = ("role", "content", "search_query", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "updated_at")
    search_fields = ("title",)
    inlines = [ChatMessageInline]
