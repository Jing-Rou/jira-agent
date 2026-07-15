import asyncio

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from triage import serializers
from model import langgraph_react_agent
from jiraToolWrapper.server import jira
from jiraToolWrapper.tools.add_issue_comment import add_issue_comment
from jiraToolWrapper.tools.create_issue import create_issue
from jiraToolWrapper.tools.create_issue_link import create_issue_link


def create_and_triage_issue(summary, description, work_type, project_key=None):
    issue = asyncio.run(create_issue(summary, description, work_type, project_key))
    ticket_key = issue.get("key") if isinstance(issue, dict) else None

    if not ticket_key:
        raise ValueError(f"Jira did not return a ticket key: {issue}")

    triage_result = langgraph_react_agent.generate_triage(ticket_key)
    output = (
        f"Created and triaged {ticket_key}.\n\n"
        f"Generated Jira comment:\n{triage_result['comment']}"
    )
    return ticket_key, triage_result, output

class JiraAgentApiView(APIView):

    def post(self, request):
        serializer = serializers.ModelRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_request = serializer.validated_data.get("request")

        try:
            result = langgraph_react_agent.invoke(user_request)

            return Response({
                "function": result.get("function"),
                "output": result.get("output"),
                "agent_trace": result.get("agent_trace", []),
                "details": result.get("details", {}),
                "draft": result.get("draft"),   
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"ERROR LangGraph JiraAgentApiView: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        return Response({'message': 'ONLINE'})
    
# async def transition_issue_to_status(issue_key, target_status):
#     transitions = await jira.get_issue_transitions(issue_key)
#     available = transitions.get("transitions", []) if transitions else []
#     target = (target_status or "").strip().lower()

#     for transition in available:
#         name = transition.get("name", "")
#         to_status = (transition.get("to") or {}).get("name", "")
#         if name.lower() == target or to_status.lower() == target:
#             await jira.transition_issue(issue_key, {
#                 "transition": {
#                     "id": transition.get("id")
#                 }
#             })
#             return {
#                 "issue_key": issue_key,
#                 "transition": name,
#                 "to_status": to_status,
#                 "success": True,
#             }

#     return {
#         "issue_key": issue_key,
#         "success": False,
#         "error": f"No available transition to {target_status}",
#         "available": [item.get("name") for item in available],
#     }
# if action_type == "transition_issues":
#                 issue_keys = request.data.get("issue_keys", [])
#                 to_status = request.data.get("to_status")

#                 if not issue_keys or not to_status:
#                     return Response(
#                         {"error": "issue_keys and to_status are required"},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )

#                 results = [
#                     asyncio.run(transition_issue_to_status(issue_key, to_status))
#                     for issue_key in issue_keys
#                 ]
#                 success_count = len([item for item in results if item.get("success")])
#                 output = f"Transitioned {success_count} of {len(issue_keys)} issues to {to_status}."

#                 return Response({
#                     "type": "issues_transitioned",
#                     "output": output,
#                     "results": results,
#                 }, status=status.HTTP_200_OK)

        
# class TriageJiraTicket(APIView):
#     """Step 2: user confirms, this actually creates the ticket and triages it."""

#     def post(self, request):
#         summary     = request.data.get("summary")
#         description = request.data.get("description")
#         work_type   = request.data.get("work_type")
#         project_key = request.data.get("project_key")
#         if not all([summary, description, work_type]):
#             return Response(
#                 {"error": "summary, description, and work_type are all required"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             ticket_key, result, output = create_and_triage_issue(
#                 summary, description, work_type, project_key
#             )

#             return Response({
#                 "type": "issue_created_and_triaged",
#                 "ticket_key": ticket_key,
#                 "output": output,
#                 "details": result,
#             }, status=status.HTTP_201_CREATED)
        
#         except Exception as e:
#             print(f"ERROR TriageJiraTicket: {e}")
#             return Response(
#                 {"error": str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
