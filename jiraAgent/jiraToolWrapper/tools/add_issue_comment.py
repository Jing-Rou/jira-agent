import mcp.types as types
from jiraToolWrapper.server import (
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
    # wrap plain string into ADF format Jira Cloud v3 expects
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": comment
                        }
                    ]
                }
            ]
        }
    }

    await jira.add_issue_comment(
        issueKey,
        payload
    )
    # print(json.dumps(json.loads(result.text), sort_keys=True, indent=4, separators=(",", ": ")))


