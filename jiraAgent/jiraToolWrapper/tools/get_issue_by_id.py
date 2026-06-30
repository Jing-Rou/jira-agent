import mcp.types as types
from jiraToolWrapper.server import (
    mcp,
    jira,
)

@mcp.tool()
async def get_issue_by_id(issueKey: str) -> tuple:
    """
        Returns the details for an issue by its identified (ID or key).
         
        Args:
            issueKey: Jira issue key to be looked up.

        Returns:
            Jira ticket data.
    """
    result = await jira.get_issue_by_id(issueKey)
    # convert JSON to Python
    key = result.get('key', [])

    fields = result.get('fields', {})
    text = jira.extract_description_text(fields.get("description"))

    return key, (fields.get('summary') + " " + text)
