import re

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from triage import serializers, models
from model.model_generate import triage, draft_issue, confirmed_create_issue

class JiraAgentApiView(APIView):

    def post(self, request):
        serializer = serializers.ModelRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_request = serializer.validated_data.get("request")

        try:
            draft  = draft_issue(user_request)
            
            if not draft.get("summary") or not draft.get("work_type"):
                return Response(
                    {"error": "Could not generate a valid draft from the request"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                "type": "issue_draft",
                "output": "I drafted a Jira issue. Please review and confirm before I create it.",
                "draft": draft,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"ERROR JiraAgentApiView: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class TriageJiraTicket(APIView):
    """Step 2: user confirms, this actually creates the ticket and triages it."""

    def post(self, request):
        summary     = request.data.get("summary")
        description = request.data.get("description")
        work_type   = request.data.get("work_type")
        print(f"summary: {summary}")
        print(f"description: {description}")
        print(f"work_type: {work_type}")

        if not all([summary, description, work_type]):
            return Response(
                {"error": "summary, description, and work_type are all required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ticket_key = confirmed_create_issue(summary, description, work_type)

            if not ticket_key:
                return Response(
                    {"error": f"Jira did not return a ticket key ({ticket_key})"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            result = triage(ticket_key)
            output = result.get("message", str(result)) if isinstance(result, dict) else str(result)

            # print("Generated Output")
            # print(f"\n{output}")

            models.TriageRecord.objects.create(
                ticket_key=ticket_key,
                request=f"{summary} | {description}",
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
        return Response({'message': 'ONLINE'})
    
class GetRecords(APIView):
    def get(self, request):
        """Get request records endpoint"""
        data = models.TriageRecord.objects.all().values()
        return Response({'result': str(data)})