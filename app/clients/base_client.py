from typing import Protocol

class BaseClient(Protocol):
    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict: ...