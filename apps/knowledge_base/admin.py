from django.contrib import admin
from .models import IssueCategory, GuidanceRule


@admin.register(IssueCategory)
class IssueCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(GuidanceRule)
class GuidanceRuleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "priority",
        "is_active",
        "created_at",
    )
    list_filter = ("category", "is_active", "created_at")
    search_fields = ("title", "condition_keywords", "guidance_text")
    ordering = ("priority", "title")
