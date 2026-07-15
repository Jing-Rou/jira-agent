"""
Jira Ticket Chatbot Agent — LangGraph version
Architecture: LangGraph ReAct-style graph (agent node <-> tools node) with
persistent conversation memory via MemorySaver checkpointing.

Install:
    pip install langgraph langchain-core langchain-ollama requests --break-system-packages

Run:
    export JIRA_BASE_URL="https://yourcompany.atlassian.net"
    export JIRA_EMAIL="you@company.com"
    export JIRA_API_TOKEN="xxxx"
    export OLLAMA_MODEL="qwen3"
    python jira_chatbot_langgraph.py
"""

# from __future__ import annotations

# import json
# import os
# import sys
# from typing import Annotated, TypedDict

# import requests
# from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
# from langchain_core.tools import tool
# from langchain_ollama import ChatOllama
# from langgraph.checkpoint.memory import MemorySaver
# from langgraph.graph import END, StateGraph
# from langgraph.graph.message import add_messages
# from langgraph.prebuilt import ToolNode, tools_condition

# # --------------------------------------------------------------------------
# # Config
# # --------------------------------------------------------------------------

# JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
# JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
# JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3")
# OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# if not (JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN):
#     print("Missing JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN environment variables.", file=sys.stderr)
#     sys.exit(1)


# # --------------------------------------------------------------------------
# # Jira REST v3 client
# # --------------------------------------------------------------------------

# class JiraClient:
#     def __init__(self, base_url: str, email: str, api_token: str):
#         self.base_url = base_url
#         self.auth = (email, api_token)
#         self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

#     def _request(self, method: str, path: str, **kwargs) -> dict:
#         url = f"{self.base_url}{path}"
#         resp = requests.request(method, url, auth=self.auth, headers=self.headers, timeout=15, **kwargs)
#         if resp.status_code >= 400:
#             return {"error": f"{resp.status_code}: {resp.text[:500]}"}
#         if resp.text.strip():
#             return resp.json()
#         return {"status": "ok"}

#     def search(self, jql: str, max_results: int = 10) -> dict:
#         payload = {"jql": jql, "maxResults": max_results, "fields": ["summary", "status", "assignee", "priority"]}
#         return self._request("POST", "/rest/api/3/search", json=payload)

#     def get_issue(self, issue_key: str) -> dict:
#         return self._request("GET", f"/rest/api/3/issue/{issue_key}")

#     def create_issue(self, project: str, summary: str, description: str, issue_type: str = "Task") -> dict:
#         payload = {
#             "fields": {
#                 "project": {"key": project},
#                 "summary": summary,
#                 "description": {
#                     "type": "doc",
#                     "version": 1,
#                     "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
#                 },
#                 "issuetype": {"name": issue_type},
#             }
#         }
#         return self._request("POST", "/rest/api/3/issue", json=payload)

#     def transition_issue(self, issue_key: str, transition_name: str) -> dict:
#         transitions = self._request("GET", f"/rest/api/3/issue/{issue_key}/transitions")
#         if "error" in transitions:
#             return transitions
#         match = next(
#             (t for t in transitions.get("transitions", []) if t["name"].lower() == transition_name.lower()),
#             None,
#         )
#         if not match:
#             available = [t["name"] for t in transitions.get("transitions", [])]
#             return {"error": f"Transition '{transition_name}' not found. Available: {available}"}
#         return self._request(
#             "POST", f"/rest/api/3/issue/{issue_key}/transitions", json={"transition": {"id": match["id"]}}
#         )

#     def add_comment(self, issue_key: str, comment: str) -> dict:
#         payload = {
#             "body": {
#                 "type": "doc",
#                 "version": 1,
#                 "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}],
#             }
#         }
#         return self._request("POST", f"/rest/api/3/issue/{issue_key}/comment", json=payload)


# jira = JiraClient(JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN)


# # --------------------------------------------------------------------------
# # LangGraph tools (plain functions decorated with @tool)
# # --------------------------------------------------------------------------

# @tool
# def jira_search(jql: str, max_results: int = 10) -> str:
#     """Search Jira issues using a JQL query. Returns matching issues (key, summary, status)."""
#     result = jira.search(jql, max_results)
#     return json.dumps(result)[:3000]


# @tool
# def jira_get_issue(issue_key: str) -> str:
#     """Get full details of a single Jira issue by its key, e.g. 'PROJ-123'."""
#     result = jira.get_issue(issue_key)
#     return json.dumps(result)[:3000]


# @tool
# def jira_create_issue(project: str, summary: str, description: str, issue_type: str = "Task") -> str:
#     """Create a new Jira issue in the given project key with a summary, description, and issue type."""
#     result = jira.create_issue(project, summary, description, issue_type)
#     return json.dumps(result)


# @tool
# def jira_transition_issue(issue_key: str, transition_name: str) -> str:
#     """Change the status of a Jira issue, e.g. transition_name='Done' or 'In Progress'."""
#     result = jira.transition_issue(issue_key, transition_name)
#     return json.dumps(result)


# @tool
# def jira_add_comment(issue_key: str, comment: str) -> str:
#     """Add a comment to a Jira issue by its key."""
#     result = jira.add_comment(issue_key, comment)
#     return json.dumps(result)


# TOOLS = [jira_search, jira_get_issue, jira_create_issue, jira_transition_issue, jira_add_comment]


# # --------------------------------------------------------------------------
# # Graph state
# # --------------------------------------------------------------------------

# class AgentState(TypedDict):
#     messages: Annotated[list, add_messages]


# SYSTEM_PROMPT = SystemMessage(
#     content=(
#         "You are a Jira ticket triage assistant. You have tools to search, read, create, "
#         "transition, and comment on Jira issues. Use them whenever a user request needs live "
#         "Jira data or an action performed. Think step by step, call tools as needed, and give a "
#         "concise final answer once you have enough information. If a tool returns an error, adapt "
#         "and try a corrected approach or explain the problem to the user."
#     )
# )

# llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
# llm_with_tools = llm.bind_tools(TOOLS)


# def agent_node(state: AgentState) -> AgentState:
#     messages = state["messages"]
#     if not any(isinstance(m, SystemMessage) for m in messages):
#         messages = [SYSTEM_PROMPT] + messages
#     response: AIMessage = llm_with_tools.invoke(messages)
#     return {"messages": [response]}


# # --------------------------------------------------------------------------
# # Build the graph
# # --------------------------------------------------------------------------

# def build_graph():
#     graph = StateGraph(AgentState)
#     graph.add_node("agent", agent_node)
#     graph.add_node("tools", ToolNode(TOOLS))

#     graph.set_entry_point("agent")
#     graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
#     graph.add_edge("tools", "agent")

#     checkpointer = MemorySaver()
#     return graph.compile(checkpointer=checkpointer)


# # --------------------------------------------------------------------------
# # CLI entry point
# # --------------------------------------------------------------------------

# def main():
#     app = build_graph()
#     thread_config = {"configurable": {"thread_id": "jira-chat-session-1"}}

#     print(f"Jira Ticket Chatbot (LangGraph, model={OLLAMA_MODEL}) ready. Type 'exit' to quit.")
#     while True:
#         try:
#             user_input = input("\nYou: ").strip()
#         except (EOFError, KeyboardInterrupt):
#             break
#         if user_input.lower() in {"exit", "quit"}:
#             break
#         if not user_input:
#             continue

#         result = app.invoke({"messages": [HumanMessage(content=user_input)]}, config=thread_config)
#         final_message = result["messages"][-1]
#         print(f"Bot: {final_message.content}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(r"C:\Users\User\Documents\JR\LLM\Jira-Agent\jiraAgent\.env")

    from langchain_community.utilities.jira import JiraAPIWrapper
    from langchain_community.agent_toolkits.jira.toolkit import JiraToolkit

    jira = JiraAPIWrapper()
    toolkit = JiraToolkit.from_jira_api_wrapper(jira)

    tools = toolkit.get_tools()

    for tool in tools:
        print("=" * 50)
        print("Tool name:", tool.name)
        print("Description:", tool.description)

        if hasattr(tool, "args"):
            print("Args:", tool.args)