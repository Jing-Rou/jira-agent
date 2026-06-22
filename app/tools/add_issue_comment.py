import json
import mcp.types as types

from dotenv import load_dotenv
from app.server import (
    mcp,
    jira,
)

@mcp.tool()
async def add_issue_comment(
    issueKey: str, 
    comment: str
) -> list[types.TextContent]:
    """
        Adds a comment to an issue.

        Args:
            primary_issue_key: Jira key of the inward issue.
            outward_issue_key: Jira key of the outward issue.
            link_type: Jira link type.

        Returns:
            None
    """
    
    result = await jira.add_issue_comment(
        issueKey,
        comment
    )

    print(json.dumps(json.loads(result.text), sort_keys=True, indent=4, separators=(",", ": ")))


