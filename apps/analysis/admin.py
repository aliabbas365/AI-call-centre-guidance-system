from django.contrib import admin
from .models import CallAnalysis


@admin.register(CallAnalysis)
class CallAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "call",
        "intent",
        "sentiment",
        "confidence_score",
        "model_name",
        "created_at",
    )
    list_filter = ("intent", "sentiment", "created_at")
    search_fields = ("guidance_text", "summary", "model_name")
    ordering = ("-created_at",)

