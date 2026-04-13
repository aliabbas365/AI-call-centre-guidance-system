from django.contrib import admin
from .models import Call, TranscriptChunk


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "caller_name",
        "caller_phone",
        "agent",
        "status",
        "started_at",
        "ended_at",
        "created_at",
    )
    list_filter = ("status", "created_at", "started_at", "ended_at")
    search_fields = ("caller_name", "caller_phone")
    ordering = ("-created_at",)


@admin.register(TranscriptChunk)
class TranscriptChunkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "call",
        "speaker",
        "sequence_number",
        "timestamp_seconds",
        "created_at",
    )
    list_filter = ("speaker", "created_at")
    search_fields = ("text",)
    ordering = ("call", "sequence_number")
