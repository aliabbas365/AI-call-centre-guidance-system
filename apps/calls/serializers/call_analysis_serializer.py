from rest_framework import serializers
from apps.analysis.models import CallAnalysis


class CallAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallAnalysis
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")