import os
import asyncio
import mcp.types as types

from dotenv import load_dotenv
from jiraToolWrapper.server import (
    mcp,
    jira,
)

@mcp.tool()
async def get_unsolved_ticket(params_query: dict) -> dict[str, str]:
    """Get all unresolved Jira tickets for a Jira project (maximum 1000). 

    Args:
        params_query (dict): The query parameters for fetching unsolved tickets.

    Returns:
        A dictionary of Jira key, description and summary data.

    """

    result = await jira.get_unsolved_ticket(params_query)
    # print(result)
    # convert JSON to Python
    issues = result.get('issues', [])

    results = []
    for issue in issues:
        key = issue.get('key', [])
        fields = issue.get('fields', {})

        summary = fields.get("summary", "")
        description  = jira.extract_description_text(fields.get("description"))
        # description  = (fields.get('summary') + " " + text)
        status_data = fields.get("status") or {}
        priority_data = fields.get("priority") or {}
        assignee_data = fields.get("assignee") or {}
        issue_type_data = fields.get("issuetype") or {}

        results.append({
            "key": key,
            "summary": summary,
            "description": description,
            "status": status_data.get("name"),
            "priority": priority_data.get("name"),
            "assignee": assignee_data.get("displayName") if assignee_data else "Unassigned",
            "issue_type": issue_type_data.get("name"),
        })

    return results

if __name__ == "__main__":
    pass