import mcp.types as types
from app.server import (
    mcp,
    jira,
)

@mcp.tool()
async def get_unsolved_ticket(issueKey) -> list[types.TextContent]:
    """
        Returns the details for an issue by its identified (ID or key).
         
        Args:
            issueKey: Jira issue key to be looked up.

        Returns:
            Jira ticket data.
    """
    result = await jira.get_issue_by_id(issueKey)

    # convert JSON to Python
    issue = result.get('issues', [])

    fields = issue.get('fields', {})
    priority = fields.get('priority')
    text = (
        f"Key: {issue.get('key')}\n"
        f"Summary: {fields.get('summary')}\n"
        f"Description: {fields.get('description')}\n"
        f"Status: {fields.get('status', {}).get('name')}\n"
        f"Priority: {priority.get('name') if priority else None}\n"
    )

    return [types.TextContent(type="text", text=text)]
