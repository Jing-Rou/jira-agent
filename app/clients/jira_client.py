import httpx
import certifi

from app.logs.logger import logger
from dataclasses import dataclass

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
        # create HTTP Headers
        header = {"Accept": "application/json"}
        url = f"{self.base_url}{endpoint}"

        try:
            # create http client
            async with httpx.AsyncClient(
                verify=certifi.where() # verify SSL certificates -> ensure You are really talking to Atlassian.
            ) as client:
                # get request to jira 
                resp = await client.get(
                    url, 
                    auth=(self.email, self.api_token),
                    params=params,
                    headers=header
                    )
                # check for errors -> 200: ok
                resp.raise_for_status()

                return resp.json()

        except Exception as e:
            logger.error(f"get_authenticate_users error: {e}")

    async def post(
            self,
            endpoint: str,
            payload: dict,
    ):  
        # create HTTP Headers
        header = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}{endpoint}"

        try:
            # create http client
            async with httpx.AsyncClient(
                verify=certifi.where() # verify SSL certificates -> ensure You are really talking to Atlassian.
            ) as client:
                # get request to jira 
                resp = await client.post(
                    url, 
                    auth=(self.email, self.api_token),
                    json=payload,
                    headers=header
                    )
                # check for errors -> 200: ok
                resp.raise_for_status()

                return resp.json()

        except Exception as e:
            logger.error(f"get_authenticate_users error: {e}")

    async def get_unsolved_ticket(
            self,
            params: dict | None = None,
        ) -> dict:
            logger.info("retrieve_unsolved_ticket called")

            return await self.get(
                f"/rest/api/3/search/jql/",
                params=params
            )
    
    async def create_issue_link(
            self, 
            payload: dict | None = None
        ) -> dict:
        logger.info("create_issue_link called")

        return await self.post(
            "rest/api/3/issueLink",
            payload
        )
             
    async def get_issue_by_id(
            self, 
            issueKey: str
        ) -> dict:
        logger.info("get_issue_by_id called")

        return await self.get(
            f"rest/api/3/issue/{issueKey}",
        )

    async def add_issue_comment(
            self,
            issueKey: str,
            payload: dict | None = None
    ) -> dict:
        logger.info("add_issue_comment called")

        return await self.post(
            f"rest/api/3/issue/{issueKey}/comment",
            payload
        )
        
