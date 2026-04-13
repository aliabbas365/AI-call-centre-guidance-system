from rest_framework import serializers
from apps.calls.models import Call


class CallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Call
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")