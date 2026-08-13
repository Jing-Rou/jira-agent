from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from jiraAgent.model.agent import _decode_tool_result
from model.tools import TOOLS, _search_jira_tickets


class AgentToolTests(SimpleTestCase):
    def test_only_confirmation_safe_tools_are_exposed(self):
        names = {agent_tool.name for agent_tool in TOOLS}

        self.assertIn("draft_issue", names)
        self.assertIn("search_knowledge_base", names)
        self.assertNotIn("jira_add_issue_comment", names)

    @patch("model.tools.get_unsolved_ticket", new_callable=AsyncMock)
    def test_search_uses_requested_project_and_filters(self, get_tickets):
        get_tickets.return_value = [{"key": "SCRUM-1"}]

        result = _search_jira_tickets(
            project_key="SCRUM",
            status="To Do",
            assignee="me",
            max_results=25,
        )

        self.assertEqual(result["count"], 1)
        params = get_tickets.await_args.args[0]
        self.assertEqual(params["maxResults"], 25)
        self.assertEqual(
            params["jql"],
            'project = "SCRUM" AND status = "To Do" '
            "AND assignee = currentUser() ORDER BY created DESC",
        )

    def test_tool_dictionary_content_is_decoded(self):
        result = _decode_tool_result('{"type": "create_issue", "summary": "Test"}')
        self.assertEqual(result["summary"], "Test")
