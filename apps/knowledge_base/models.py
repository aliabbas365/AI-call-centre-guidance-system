from django.db import models


class IssueCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Issue Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class GuidanceRule(models.Model):
    category = models.ForeignKey(
        IssueCategory,
        on_delete=models.CASCADE,
        related_name="guidance_rules",
    )
    title = models.CharField(max_length=255)
    condition_keywords = models.TextField(
        help_text="Comma-separated keywords, e.g. refund,payment,invoice"
    )
    guidance_text = models.TextField()
    priority = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "title"]

    def __str__(self):
        return f"{self.title} ({self.category.name})"
