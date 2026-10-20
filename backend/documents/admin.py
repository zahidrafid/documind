from django.contrib import admin

from .models import Chunk, Document


class ChunkInline(admin.TabularInline):
    model = Chunk
    fields = ("page_number", "chunk_index", "text")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "page_count", "uploaded_at")
    list_filter = ("status",)
    search_fields = ("title",)
    inlines = [ChunkInline]


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "page_number", "chunk_index")
    list_filter = ("document",)
    exclude = ("embedding",)
