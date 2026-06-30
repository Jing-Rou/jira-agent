from fastmcp import FastMCP
from jiraToolWrapper.jira_client import get_jira_client

mcp = FastMCP("Jira MCP Server")
jira = get_jira_client()