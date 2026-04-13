from django.db import models


class CallAnalysis(models.Model):
    INTENT_CHOICES = [
        ("technical_issue", "Technical Issue"),
        ("billing", "Billing"),
        ("complaint", "Complaint"),
        ("insurance_inquiry", "Insurance Inquiry"),
        ("general_inquiry", "General Inquiry"),
        ("other", "Other"),
    ]

    SENTIMENT_CHOICES = [
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("negative", "Negative"),
        ("frustrated", "Frustrated"),
        ("angry", "Angry"),
    ]

    call = models.OneToOneField(
        "calls.Call",
        on_delete=models.CASCADE,
        related_name="analysis",
    )
    intent = models.CharField(max_length=50, choices=INTENT_CHOICES, default="other")
    sentiment = models.CharField(max_length=50, choices=SENTIMENT_CHOICES, default="neutral")
    confidence_score = models.FloatField(blank=True, null=True)
    guidance_text = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    processing_time_seconds = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Analysis for Call #{self.call.id}"