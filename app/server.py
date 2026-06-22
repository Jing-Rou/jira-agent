from fastmcp import FastMCP
from app.clients.factory import get_jira_client

mcp = FastMCP("Jira MCP Server")
jira = get_jira_client()