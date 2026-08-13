import asyncio
import traceback
import logging
logger = logging.getLogger(__name__)

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from triage import serializers
from jiraToolWrapper.server import jira
from jiraToolWrapper.jira_client import JiraAPIError
from jiraToolWrapper.tools.add_issue_comment import add_issue_comment
from jiraToolWrapper.tools.create_issue import create_issue
from jiraToolWrapper.tools.create_issue_link import create_issue_link


def create_and_triage_issue(summary, description, work_type, project_key=None):
    from model.tools import generate_triage_data

    issue = asyncio.run(create_issue(summary, description, work_type, project_key))
    ticket_key = issue.get("key") if isinstance(issue, dict) else None

    if not ticket_key:
        raise ValueError(f"Jira did not return a ticket key: {issue}")

    triage_result = generate_triage_data(ticket_key)
    output = (
        f"Created and triaged {ticket_key}.\n\n"
        f"Generated Jira comment:\n{triage_result['comment']}"
    )
    return ticket_key, triage_result, output

class JiraAgentApiView(APIView):

    def post(self, request):
        from model.agent import invoke as invoke_jira_agent

        logger.info("Jira agent request received")

        serializer = serializers.ModelRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_request = serializer.validated_data.get("request")
        thread_id = serializer.validated_data.get("thread_id")

        logger.info(
            "Invoking agent thread_id=%s request=%r",
            thread_id,
            user_request[:500],
        )
            
        try:
            result = invoke_jira_agent(user_request=user_request, thread_id=thread_id)
            logger.info(
                "Agent completed thread_id=%s tools=%s",
                result.get("thread_id"),
                [item.get("function") for item in result.get("agent_trace", [])],
            )

            return Response(
                {
                    "function": result.get("function"),
                    "output": result.get("output", ""),
                    "draft": result.get("draft"),
                    "triage": result.get("triage"),
                    "agent_trace": result.get("agent_trace", []),
                    "thread_id": result.get("thread_id"),
                }, 
                status=status.HTTP_200_OK
            )

        except JiraAPIError as error:
            return Response(
                {
                    "error": str(error),
                    "type": "jira_api_error",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as error:
            print("Agent error:", repr(error))
            print(traceback.format_exc())

            return Response(
                {"error": str(error), "type": "agent_error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class ConfirmedJiraAction(APIView):
    """Executes a write action only after the user confirms a draft."""

    def post(self, request):
        try:
            action_type = request.data.get("function_name")
            print(f"data: {request.data.get("function_name")}")
            
            if action_type == "draft_issue":
                summary = request.data.get("summary")
                description = request.data.get("description")
                work_type = request.data.get("work_type")
                project_key = request.data.get("project_key")

                if not all([summary, description, work_type]):
                    return Response(
                        {"error": "summary, description, and work_type are required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                ticket_key, result, output = create_and_triage_issue(
                    summary, description, work_type, project_key
                )

                return Response({
                    "type": "issue_created_and_triaged",
                    "ticket_key": ticket_key,
                    "output": output,
                    "details": result,
                }, status=status.HTTP_201_CREATED)

            if action_type == "triage_ticket":
                ticket_key = request.data.get("ticket_key")
                comment = request.data.get("comment")

                if not all([ticket_key, comment]):
                    return Response(
                        {"error": "ticket_key and comment are required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                asyncio.run(add_issue_comment(ticket_key, comment))
                output = f"Comment added to {ticket_key}."

                return Response({
                    "type": "comment_added",
                    "ticket_key": ticket_key,
                    "output": output,
                }, status=status.HTTP_200_OK)

            if action_type == "link_issues":
                source_key = request.data.get("source_key")
                target_key = request.data.get("target_key")
                link_type = request.data.get("link_type", "Relates")

                if not all([source_key, target_key, link_type]):
                    return Response(
                        {"error": "source_key, target_key, and link_type are required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                asyncio.run(create_issue_link(source_key, target_key, link_type))
                output = f"Linked {source_key} to {target_key} as {link_type}."

                return Response({
                    "type": "issues_linked",
                    "output": output,
                    "source_key": source_key,
                    "target_key": target_key,
                    "link_type": link_type,
                }, status=status.HTTP_200_OK)

            return Response(
                {"error": f"Unsupported confirmed action: {action_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            print(f"ERROR ConfirmJiraAction: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HealthCheck(APIView):
    def get(self, request):
        """Healthcheck endpoint"""
        print(f"data: {request.data.get('function_name')}")
        return Response({'message': 'ONLINE'})