import os
from jiraToolWrapper.server import (
    mcp,
    jira,
)

@mcp.tool()
async def create_issue(
    summary: str,
    description: str,
    work_type: str,
):
    
    print(f"summary: {summary}")
    # wrap plain string into ADF format Jira Cloud v3 expects
    payload = {
        "fields": {
            "project": {
                "key": os.getenv("PROJECT_KEY", "SCRUM")
            },
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {
                "name": work_type
            }
        }
    }

    response = await jira.create_issue(payload) 

    return response