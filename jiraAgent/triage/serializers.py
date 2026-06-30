from rest_framework import serializers
from triage.models import TriageRecord

class ModelRequestSerializer(serializers.Serializer):
    request = serializers.CharField(
        required = True,
        error_messages = {
            "required": "request field is required.",
            "blank": "request field cannot be blank.",
            }
        )

class ModelResponseSerializer(serializers.Serializer):
    class Meta:
        model = TriageRecord
        fields = ["ticket_key", "request", "response", "created_at"]