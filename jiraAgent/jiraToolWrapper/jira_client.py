import os
from dataclasses import dataclass
from typing import Protocol

import certifi
import httpx
from dotenv import load_dotenv

from jiraToolWrapper.logs.logger import logger

class BaseClient(Protocol):
    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict: ...

@dataclass
class JiraClient:
    base_url: str
    email: str
    api_token: str

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ):
        headers = {"Accept": "application/json"}
        url = f"{self.base_url}{endpoint}"

        try:
            async with httpx.AsyncClient(verify=certifi.where()) as client:
                resp = await client.get(
                    url,
                    auth=(self.email, self.api_token),
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"jira get error: {e}")

    async def post(
        self,
        endpoint: str,
        payload: dict,
    ):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{endpoint}"

        try:
            async with httpx.AsyncClient(verify=certifi.where()) as client:
                resp = await client.post(
                    url,
                    auth=(self.email, self.api_token),
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()

                if resp.content:
                    return resp.json()
                return {}
        except Exception as e:
            logger.error(f"jira post error: {e}")

    @staticmethod
    def extract_description_text(description: dict) -> str:
        """Recursively extracts all text from Atlassian Document Format (ADF)."""
        if not description:
            return ""

        texts = []

        def walk(node):
            if not isinstance(node, dict):
                return
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            if node.get("type") in ("paragraph", "listItem", "bulletList", "orderedList", "heading"):
                texts.append("\n")
            for child in node.get("content", []):
                walk(child)

        walk(description)
        return " ".join(texts).strip()

    async def get_unsolved_ticket(
        self,
        params: dict | None = None,
    ) -> dict:
        logger.info("retrieve_unsolved_ticket called")
        return await self.get("/rest/api/3/search/jql/", params=params)

    async def create_issue_link(
        self,
        payload: dict | None = None,
    ) -> dict:
        logger.info("create_issue_link called")
        return await self.post("/rest/api/3/issueLink", payload)

    async def get_issue_by_id(
        self,
        issueKey: str,
    ) -> dict:
        logger.info("get_issue_by_id called")
        return await self.get(f"/rest/api/3/issue/{issueKey}")

    async def add_issue_comment(
        self,
        issueKey: str,
        payload: dict | None = None,
    ) -> dict:
        logger.info("add_issue_comment called")
        return await self.post(f"/rest/api/3/issue/{issueKey}/comment", payload)

    async def create_issue(
        self,
        payload: dict | None = None,
    ) -> dict:
        logger.info("create_issue called")
        return await self.post("/rest/api/3/issue/", payload)


def get_jira_client() -> BaseClient:
    load_dotenv()

    return JiraClient(
        base_url=os.getenv("JIRA_INSTANCE_URL"),
        email=os.getenv("JIRA_USERNAME"),
        api_token=os.getenv("JIRA_API_TOKEN"),
    )