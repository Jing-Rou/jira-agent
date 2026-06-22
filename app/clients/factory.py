import os
from dotenv import load_dotenv

from app.clients.jira_client import JiraClient
from app.clients.base_client import BaseClient

def get_jira_client() -> BaseClient:
    load_dotenv()

    return JiraClient(
        base_url=os.getenv("JIRA_HOST"),
        email=os.getenv("JIRA_EMAIL"),
        api_token=os.getenv("JIRA_API_TOKEN"),
    )
