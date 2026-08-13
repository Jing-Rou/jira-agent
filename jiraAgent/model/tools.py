"""LangChain tools exposed to the Jira ReAct agent.

Plain implementation functions are kept separate from ``@tool`` wrappers so
they can also be called safely by Django views and unit tests.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Literal

from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from jiraToolWrapper.tools.get_issue_by_id import get_issue_by_id
from jiraToolWrapper.tools.get_unsolved_ticket import get_unsolved_ticket
from model.knowledge_base import (
    INSUFFICIENT_CONTEXT,
    KnowledgeBaseNotInitialized,
    generate_answer,
    search,
)
from .llm import create_issue_model, product_model
from langchain_community.utilities.jira                 import JiraAPIWrapper
from langchain_community.agent_toolkits.jira.toolkit    import JiraToolkit

load_dotenv()


class IssueKeyInput(BaseModel):
    """Input shared by tools that operate on one Jira issue."""

    ticket_key: str = Field(
        min_length=1,
        description="Jira issue key, for example SCRUM-5.",
        examples=["SCRUM-5"],
    )


class SearchJiraTicketsInput(BaseModel):
    """Filters for searching Jira issues."""

    project_key: str = Field(
        default="",
        description=(
            "Jira project key, for example SCRUM or AAT. If omitted, the "
            "application's configured PROJECT_KEY is used."
        ),
        examples=["SCRUM"],
    )
    status: str = Field(
        default="",
        description="Jira status, for example To Do, In Progress, or Done.",
        examples=["To Do"],
    )
    assignee: str = Field(
        default="",
        description=(
            "Assignee display name, or 'me'/'currentUser' for the current "
            "authenticated Jira user."
        ),
        examples=["me"],
    )
    resolution: str = Field(
        default="",
        description=(
            "Jira resolution filter. Use 'unresolved' (or 'none'/'open'/'pending') "
            "for issues with no resolution set. Use 'resolved' (or 'closed') for any "
            "issue that has a resolution set, regardless of which one. Otherwise "
            "pass an exact resolution name — common values are Done, Won't Do, "
            "Duplicate, Cannot Reproduce, or Fixed, though your Jira instance may "
            "have custom ones."
        ),
        examples=["unresolved", "resolved", "Done"],
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum number of Jira issues to return, from 1 to 1000.",
    )


class CountJiraTicketsInput(BaseModel):
    """Filters for counting Jira issues."""

    project_key: str = Field(
        default="",
        description=(
            "Jira project key, for example SCRUM or AAT. If omitted, the "
            "application's configured PROJECT_KEY is used."
        ),
        examples=["SCRUM"],
    )
    status: str = Field(
        default="",
        description="Jira status, for example To Do, In Progress, or Done.",
        examples=["Done"],
    )
    assignee: str = Field(
        default="",
        description=(
            "Assignee display name, or 'me'/'currentUser' for the current "
            "authenticated Jira user."
        ),
        examples=["me"],
    )
    resolution: str = Field(
        default="",
        description=(
            "Jira resolution filter. Use 'unresolved' (or 'none'/'open'/'pending') "
            "for issues with no resolution set. Use 'resolved' (or 'closed') for any "
            "issue that has a resolution set, regardless of which one. Otherwise "
            "pass an exact resolution name — common values are Done, Won't Do, "
            "Duplicate, Cannot Reproduce, or Fixed, though your Jira instance may "
            "have custom ones."
        ),
        examples=["unresolved", "resolved", "Done"],
    )


class DraftIssueInput(BaseModel):
    """Natural-language request used to prepare an issue draft."""

    user_request: str = Field(
        min_length=1,
        description=(
            "Prepare a Jira issue draft whenever the user describes new work that "
            "should be tracked — an explicit request ('create/open/raise/file/report a "
            "ticket'), OR a stated task/feature/improvement they want done ('add X', "
            "'we should implement Y', 'set up Z'). Pass the user's FULL original "
            "wording as user_request, even if brief — do not wait for a fully detailed "
            "bug report before calling this tool.\n"
            "Examples: 'create a bug because the database connection fails during "
            "startup' | 'add agent evaluation into the workflow' | 'we need retry "
            "logic on the Jira API calls'."
        ),
    )


JiraWorkType = Literal[
    "Bug",
    "Task",
    "Story",
    "Epic",
    "Setup Jira MCP Server",
    "Feature",
    "Request",
]


class DraftIssueOutput(BaseModel):
    """Validated issue draft returned to the confirmation workflow."""

    type: Literal["create_issue"]
    project_key: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)
    work_type: JiraWorkType


class KnowledgeBaseSearchInput(BaseModel):
    """Input for searching uploaded support documents."""

    query: str = Field(
        min_length=1,
        description="Complete question to answer from the knowledge base.",
    )
    category: str = Field(
        default="general",
        description="Document category to search; use 'general' by default.",
    )


def extract_tag(text: str, tag: str) -> str | None:
    """Extract one XML-like tag from a model response."""
    match = re.search(
        rf"<{re.escape(tag)}>(.*?)</{re.escape(tag)}>",
        text,
        flags=re.DOTALL,
    )
    return match.group(1).strip() if match else None


def _escape_jql(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _get_issue_detail(ticket_key: str) -> dict[str, Any]:
    issue_key, issue_data = asyncio.run(get_issue_by_id(ticket_key.strip()))
    return {"key": issue_key, "data": issue_data}


@tool(args_schema=IssueKeyInput)
def get_issue_detail(ticket_key: str) -> dict[str, Any]:
    """Fetch current details for exactly one existing Jira issue. Read-only."""
    return _get_issue_detail(ticket_key)


def _search_jira_tickets(
    project_key: str = "",
    status: str = "",
    assignee: str = "",
    resolution: str = "",
    max_results: int = 10,
) -> dict[str, Any]:
    clauses: list[str] = []
    effective_project = project_key.strip() or os.getenv("PROJECT_KEY", "").strip()

    if effective_project:
        clauses.append(f'project = "{_escape_jql(effective_project)}"')

    if status:
        clauses.append(f'status = "{_escape_jql(status.strip())}"')

    if assignee:
        normalized_assignee = assignee.strip()
        if normalized_assignee.lower() in {"me", "myself", "currentuser"}:
            clauses.append("assignee = currentUser()")
        else:
            clauses.append(
                f'assignee = "{_escape_jql(normalized_assignee)}"'
            )

    if not clauses:
        raise ValueError(
            "A Jira search requires project_key, status, or assignee. "
            "Set PROJECT_KEY or provide at least one filter."
        )

    if resolution:
        normalized_resolution = resolution.strip()
        if normalized_resolution.lower() in {"unresolved", "none", "open"}:
            # Jira's own convention: an unresolved issue has resolution = EMPTY,
            # not a resolution named "Unresolved" — this is not a quoted string match.
            clauses.append("resolution = EMPTY")
        else:
            clauses.append(f'resolution = "{_escape_jql(normalized_resolution)}"')

    jql = " AND ".join(clauses) + " ORDER BY created DESC"
    limit = max(1, min(int(max_results), 1000))

    params_query = {
        "jql": jql,
        "maxResults": limit,
        "fields": "summary,description,status,assignee,priority,issuetype",
    }
    tickets = asyncio.run(get_unsolved_ticket(params_query))

    return {
        "jql": jql,
        "count": len(tickets),
        "tickets": tickets,
    }


@tool(args_schema=SearchJiraTicketsInput)
def search_jira_tickets(
    project_key: str = "",
    status: str = "",
    assignee: str = "",
    resolution: str = "",
    max_results: int = 10,
) -> dict[str, Any]:
    """Return live Jira issue details matching filters. Use count_jira_tickets when the user only asks how many. Read-only."""
    return _search_jira_tickets(
        project_key=project_key,
        status=status,
        assignee=assignee,
        resolution=resolution,
        max_results=max_results,
    )


@tool(args_schema=CountJiraTicketsInput)
def count_jira_tickets(
    project_key: str = "",
    status: str = "",
    assignee: str = "",
    resolution: str = "",
) -> dict[str, Any]:
    """Count live Jira issues matching filters. Use this for 'how many' questions. Read-only."""
    result = _search_jira_tickets(
        project_key=project_key,
        status=status,
        assignee=assignee,
        resolution=resolution,  
        max_results=1000,
    )
    return {"jql": result["jql"], "count": result["count"]}


def generate_triage_data(ticket_key: str) -> dict[str, Any]:
    """Generate a proposed triage comment without modifying Jira."""
    primary_issue_key, primary_issue_data = asyncio.run(
        get_issue_by_id(ticket_key.strip())
    )
    llm_result = product_model.generator(
        f"<description>{primary_issue_data}</description>"
    )

    user_stories = extract_tag(llm_result, "user_stories") or ""
    acceptance_criteria = extract_tag(llm_result, "acceptance_criteria") or ""
    priority = extract_tag(llm_result, "priority") or ""
    thought = extract_tag(llm_result, "thought") or ""
    comment = (
        f"user_stories: {user_stories}\n"
        f"acceptance_criteria: {acceptance_criteria}\n"
        f"priority: {priority}\n"
        f"thought: {thought}"
    )

    return {
        "ticket_key": primary_issue_key,
        "user_stories": user_stories,
        "acceptance_criteria": acceptance_criteria,
        "priority": priority,
        "thought": thought,
        "comment": comment,
    }


@tool(args_schema=IssueKeyInput)
def generate_triage(ticket_key: str) -> dict[str, Any]:
    """Draft triage data and a proposed comment for one issue. Does not modify Jira."""
    return generate_triage_data(ticket_key)


def _draft_issue(user_request: str) -> dict[str, Any]:
    llm_output = create_issue_model.generator(
        f"<description>{user_request.strip()}</description>"
    )
    draft = {
        "type": "create_issue",
        "project_key": os.getenv("PROJECT_KEY", ""),
        "summary": extract_tag(llm_output, "summary") or "",
        "description": extract_tag(llm_output, "description") or "",
        "work_type": extract_tag(llm_output, "work_type") or "",
    }

    missing_fields = [
        field
        for field in ("summary", "description", "work_type")
        if not draft[field]
    ]
    if missing_fields:
        raise ValueError(
            "Draft is missing required fields: " + ", ".join(missing_fields)
        )

    return DraftIssueOutput.model_validate(draft).model_dump()


@tool(args_schema=DraftIssueInput)
def draft_issue(user_request: str) -> dict[str, Any]:
    """Prepare a Jira issue draft only when creation is requested. Requires user confirmation and does not create the issue."""
    return _draft_issue(user_request)


def _search_knowledge_base(
    query: str,
    category: str = "general",
) -> dict[str, Any]:
    """Run persistent RAG retrieval and grounded answer generation."""
    try:
        chunks = search(query, category)
    except KnowledgeBaseNotInitialized as error:
        return {
            "available": False,
            "sufficient": False,
            "answer": INSUFFICIENT_CONTEXT,
            "chunks": [],
            "error": str(error),
        }

    if not chunks:
        return {
            "available": True,
            "sufficient": False,
            "answer": INSUFFICIENT_CONTEXT,
            "chunks": [],
            "error": "No relevant knowledge-base chunks were retrieved.",
        }

    answer = generate_answer(query, chunks).strip()
    sufficient = not answer.upper().startswith(INSUFFICIENT_CONTEXT)
    return {
        "available": True,
        "sufficient": sufficient,
        "answer": answer,
        "chunks": chunks,
        "error": "" if sufficient else "The retrieved context was insufficient.",
    }


@tool(args_schema=KnowledgeBaseSearchInput)
def search_knowledge_base(
    query: str,
    category: str = "general",
) -> dict[str, Any]:
    """Answer documentation, policy, and troubleshooting questions from uploaded support documents. Do not use for live Jira data."""
    return _search_knowledge_base(query, category)


jira_wrapper = JiraAPIWrapper()
toolkit = JiraToolkit.from_jira_api_wrapper(jira_wrapper)
jira_toolkit_tools = toolkit.get_tools()
    
# The complete catalogue is useful for discovery and tests. The fallback ReAct
# agent receives only JIRA_TOOLS because the outer graph has already attempted
# knowledge retrieval before it is allowed to reach Jira.
JIRA_TOOLS = [
    get_issue_detail,
    search_jira_tickets,
    count_jira_tickets,
    generate_triage,
    draft_issue,
]
TOOLS = [search_knowledge_base, *JIRA_TOOLS, *jira_toolkit_tools]
