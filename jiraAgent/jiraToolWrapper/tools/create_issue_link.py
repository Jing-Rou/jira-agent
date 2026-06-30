import mcp.types as types
from jiraToolWrapper.server import (
    mcp,
    jira,
)

@mcp.tool()
async def create_issue_link(
    inward_issue_key: str, 
    outward_issue_key: str, 
    link_type: str='Relates'
) -> list[types.TextContent]:
    """
        Creates a relationship between two issues by linking between two of them
        and optionally add a comment to the from (outward) issue.

        Args:
            primary_issue_key: Jira key of the inward issue.
            outward_issue_key: Jira key of the outward issue.
            link_type: Jira link type.

        Returns:
            None
    """

    payload = {
        "type": {
            "name": link_type
        },
        "inwardIssue": {
            "key": inward_issue_key
        },
        "outwardIssue": {
            "key": outward_issue_key
        }
    }

    result = await jira.create_issue_link(payload)

    # print(json.dumps(json.loads(result.text), sort_keys=True, indent=4, separators=(",", ": ")))



