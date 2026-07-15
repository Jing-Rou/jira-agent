from rest_framework import serializers

class ModelRequestSerializer(serializers.Serializer):
    request = serializers.CharField(
        required = True,
        error_messages = {
            "required": "request field is required.",
            "blank": "request field cannot be blank.",
            }
        )

