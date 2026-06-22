import os
import mcp.types as types

from dotenv import load_dotenv
from app.server import (
    mcp,
    jira,
)

@mcp.tool()
async def get_unsolved_ticket() -> list[types.TextContent]:
    """Get all unresolved Jira tickets for a Jira project (maximum 1000). 

    Args:
        None

    Returns:
        A dictionary of Jira key, description and summary data.
    """
    load_dotenv()

    params_query = {
        'jql': f'project = {os.getenv("PROJECT_KEY")} AND resolution = Unresolved ORDER BY created DESC',
        'maxResults': 1000,
        'fields': 'summary,description,status,priority'
    }

    result = await jira.retrieve_unsolved_ticket(params_query)

    # convert JSON to Python
    issues = result.get('issues', [])

    results = []
    for issue in issues:
        fields = issue.get('fields', {})
        priority = fields.get('priority')
        text = (
            f"Key: {issue.get('key')}\n"
            f"Summary: {fields.get('summary')}\n"
            f"Description: {fields.get('description')}\n"
            f"Status: {fields.get('status', {}).get('name')}\n"
            f"Priority: {priority.get('name') if priority else None}\n"
        )
        results.append(types.TextContent(type="text", text=text))

    return results

# if __name__ == "__main__":
#     results = asyncio.run(get_unsolved_ticket())
#     for item in results:
#         print(item.text)
#         print("-" * 50)