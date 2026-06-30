import re

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from triage import serializers, models
from model.model_generate import triage, draft_issue

class JiraAgentApiView(APIView):

    def post(self, request):
        serializer = serializers.ModelRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_request = serializer.validated_data.get("request")
        
        try:
            ticket_key = draft_issue(user_request)
            if not ticket_key:
                return Response(
                    {"error": "Jira did not return a ticket key"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            result = triage(ticket_key)
            output = result.get("message", str(result)) if isinstance(result, dict) else str(result)

            # print("Generated Output")
            # print(f"\n{output}")

            models.TriageRecord.objects.create(
                ticket_key=ticket_key,
                request=user_request,
                response=output,
            )

            return Response({
                "type": "issue_created_and_triaged",
                "ticket_key": ticket_key,
                "output": output,
                "details": result,
            }, status=status.HTTP_201_CREATED)
    
        except Exception as e:
            print(f"ERROR JiraAgentApiView: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class HealthCheck(APIView):
    def get(self, request):
        """Healthcheck endpoint"""
        return Response({'message': 'OK'})
    
class GetRecords(APIView):
    def get(self, request):
        """Get request records endpoint"""
        data = models.TriageRecord.objects.all().values()
        return Response({'result': str(data)})