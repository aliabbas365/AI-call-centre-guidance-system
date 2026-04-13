from django.conf import settings
from django.db import models


class Call(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("uploading", "Uploading"),
        ("transcribing", "Transcribing"),
        ("analyzing", "Analyzing"),
        ("live", "Live"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    caller_name = models.CharField(max_length=255, blank=True, null=True)
    caller_phone = models.CharField(max_length=50, blank=True, null=True)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    audio_file = models.FileField(upload_to="call_audio/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Call #{self.id} - {self.caller_name or 'Unknown Caller'}"


class LiveCallSession(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("stopped", "Stopped"),
        ("failed", "Failed"),
    ]

    call = models.OneToOneField(
        Call,
        on_delete=models.CASCADE,
        related_name="live_session",
    )
    session_key = models.CharField(max_length=100, unique=True)
    sample_rate = models.PositiveIntegerField(default=16000)
    channels = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    pcm_buffer = models.BinaryField(blank=True, null=True)
    last_sequence_number = models.PositiveIntegerField(default=0)
    last_transcript_text = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"LiveSession call={self.call_id} status={self.status}"


class TranscriptChunk(models.Model):
    SPEAKER_CHOICES = [
        ("caller", "Caller"),
        ("agent", "Agent"),
        ("system", "System"),
    ]

    SOURCE_CHOICES = [
        ("recorded_upload", "Recorded Upload"),
        ("live_stream", "Live Stream"),
        ("manual", "Manual"),
        ("system", "System"),
    ]

    call = models.ForeignKey(
        Call,
        on_delete=models.CASCADE,
        related_name="transcript_chunks",
    )
    speaker = models.CharField(max_length=20, choices=SPEAKER_CHOICES, default="caller")
    text = models.TextField()
    sequence_number = models.PositiveIntegerField(default=1, db_index=True)
    timestamp_seconds = models.FloatField(blank=True, null=True)
    is_partial = models.BooleanField(default=False)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="manual", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence_number", "created_at"]

    def __str__(self):
        return f"TranscriptChunk #{self.id} for Call #{self.call.id}"