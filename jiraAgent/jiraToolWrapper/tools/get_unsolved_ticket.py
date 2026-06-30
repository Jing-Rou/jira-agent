import os
import mcp.types as types

from dotenv import load_dotenv
from jiraToolWrapper.server import (
    mcp,
    jira,
)

@mcp.tool()
async def get_unsolved_ticket() -> dict[str, str]:
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

    result = await jira.get_unsolved_ticket(params_query)
    # print(result)
    # convert JSON to Python
    issues = result.get('issues', [])

    results = {}
    for issue in issues:
        key = issue.get('key', [])
        fields = issue.get('fields', {})

        text = jira.extract_description_text(fields.get("description"))
        results[key] = (fields.get('summary') + " " + text)
        
    return results

# if __name__ == "__main__":
    # results = asyncio.run(get_unsolved_ticket())
    # for item in results:
    #     print(item.text)
    #     print("-" * 50)