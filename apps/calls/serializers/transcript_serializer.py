from rest_framework import serializers
from apps.calls.models import TranscriptChunk


class TranscriptChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranscriptChunk
        fields = "__all__"
        read_only_fields = ("created_at",)