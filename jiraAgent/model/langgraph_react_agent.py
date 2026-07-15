import xml.etree.ElementTree as ET
import operator
import asyncio
import os
import re

from typing                                             import Any, Union
from dotenv                                             import load_dotenv
from typing                                             import TypedDict, Annotated
from dotenv                                             import load_dotenv

from langgraph.graph                                    import StateGraph, END
from langchain_community.utilities.jira                 import JiraAPIWrapper
from langchain_community.agent_toolkits.jira.toolkit    import JiraToolkit
from langchain.agents                                   import create_agent
from langchain_ollama                                   import ChatOllama

from model.system_prompts                               import PROMPTS as system_prompts
from model.llm                                          import reAct_agent_model, linking_model, product_model, create_issue_model
from jiraToolWrapper.tools.create_issue_link            import create_issue_link
from jiraToolWrapper.tools.get_issue_by_id              import get_issue_by_id
from jiraToolWrapper.tools.add_issue_comment            import add_issue_comment
from jiraToolWrapper.tools.get_unsolved_ticket          import get_unsolved_ticket

load_dotenv()
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))

# ----------------------------
# Optional LangChain JiraToolkit
# ----------------------------
def build_jira_toolkit_agent():

    try:
        llm = ChatOllama(
            model=os.getenv("LLM_MODEL"),
            base_url=os.getenv("LLM_BASE_URL"),
            temperature=0.2,
        )

        jira_wrapper = JiraAPIWrapper()
        toolkit = JiraToolkit.from_jira_api_wrapper(jira_wrapper)
        tools = toolkit.get_tools()

        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt="You are a Jira assistant. Use Jira tools to answer the user.",
        )
        return agent

    except Exception as e:
        print(f"JiraToolkit not available: {e}")
        return None


def run_jira_toolkit(user_request: str) -> dict:

    jira_toolkit_agent = build_jira_toolkit_agent()

    if jira_toolkit_agent is None:
        return {
            "success": False,
            "error": "JiraToolkit agent is not available. Check langchain packages, LLM config, and Jira env vars.",
        }

    try:
        result = jira_toolkit_agent.invoke({
            "messages": [
                {"role": "user", "content": user_request}
            ]
        })

        last_message = result["messages"][-1]

        return {
            "success": True,
            "result": getattr(last_message, "content", str(last_message)),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

# ----------------------------
# LangGraph State
# ----------------------------
# Define the state that flows through our graph
# function is for behavior
# state class is for structure, class / TypedDict = what data exists
class AgentState(TypedDict):
    user_request: str
    hist_messages: Annotated[list[str], operator.add]
    next_action: str
    final_answer: str
    iterations: int
    draft: dict | None
    last_tool_result: Any | None

# ----------------------------
# Helpers
# ----------------------------
def extract_tag(text: str, tag: str = "related") -> Union[str, None]:
    try:
        if match := re.compile(
            f"<{tag}>(.*?)</{tag}>", flags=re.DOTALL  # fixed: was <tag>...<tag>
        ).search(text):
            return match.group(1).strip()
    except Exception as e:
        print(f"ERROR extract_tag: {e}")     

def format_available_tools(tools):
    lines = []

    for name, info in tools.items():
        lines.append(f"- function name: {name}")
        lines.append(f"  Description: {info['description']}")
        lines.append("  Parameters:")

        properties = info["input_schema"]["properties"]
        required = info["input_schema"].get("required", [])

        for param_name, param_info in properties.items():
            required_text = "required" if param_name in required else "optional"
            lines.append(
                f"    - {param_name} ({param_info['type']}, {required_text}): {param_info['description']}"
            )

        lines.append("")

    return "\n".join(lines)

# ----------------------------
# Custom Jira Tools
# ----------------------------
def get_issue_detail(ticket_key: str):
    """Fetch one Jira issue by key."""
    issue_key, issue_data = asyncio.run(get_issue_by_id(ticket_key))
    return {
        "key": issue_key,
        "data": issue_data,
    }

def search_jira_tickets(
    project_key: str = "",
    status: str = "",
    assignee: str = "",
    max_results: str = "10",
) -> dict:
    """Search Jira tickets by project, status, and assignee."""

    clauses = []

    if project_key:
        clauses.append(f'project = "{os.getenv("PROJECT_KEY")}"')

    if status:
        clauses.append(f'status = "{status}"')

    if assignee:
        if assignee.lower() in ["me", "myself", "currentuser"]:
            clauses.append("assignee = currentUser()")
        else:
            clauses.append(f'assignee = "{assignee}"')

    jql = " AND ".join(clauses) if clauses else "ORDER BY created DESC"

    if clauses:
        jql = f"{jql} ORDER BY created DESC"

    params_query = {
        "jql": jql,
        "maxResults": int(max_results),
        "fields": "summary,description,status,assignee,priority,issuetype",
    }

    result = asyncio.run(get_unsolved_ticket(params_query))

    return {
        "jql": jql,
        "count": len(result),
        "tickets": result,
    }

def count_jira_tickets(
    project_key: str = "",
    status: str = "",
    assignee: str = "",
) -> dict:
    result = search_jira_tickets(
        project_key=project_key,
        status=status,
        assignee=assignee,
        max_results="100",
    )

    return {
        "jql": result["jql"],
        "count": result["count"],
    }

def search_related_issues(ticket_key: str) -> list[dict]:
    """
        Search open Jira issues and return issues related to the provided ticket key.
    """

    # related = []
    # max_candidates = int(os.getenv("MAX_RELATED_CANDIDATES", "8"))
    # checked = 0

    primary_issue_key, primary_issue_data = asyncio.run(get_issue_by_id(ticket_key))

    params_query = {
        'jql': f'project = {os.getenv("PROJECT_KEY")} AND resolution = Unresolved ORDER BY created DESC',
        'maxResults': 1000,
        'fields': 'summary,description,status,priority'
    }

    all_tickets = asyncio.run(get_unsolved_ticket(params_query))

    candidates = []

    for issue_details in all_tickets:
        candidate_key = issue_details.get("key")
        # candidate_data = issue_details.get('description') + " " + issue_details.get('summary')

        if candidate_key == primary_issue_key:
            continue

        # llm_result = linking_model.generator(
        #     f"<ticket1>{primary_issue_data}</ticket1><ticket2>{candidate_data}</ticket2>"
        # )

        # related_value = extract_tag(llm_result) or "False"
        # thought = extract_tag(llm_result, "thought") or ""
        # # convert string to actual boolean
        # is_related = related_value.strip().lower() == "true"

        # related.append({
        #     "source": primary_issue_key,
        #     "target": candidate_key,
        #     "related": is_related,
        #     "thought": thought,
        # })

        # if result.get("related"):
        #     asyncio.run(create_issue_link(primary_issue_key, candidate_key))

        # related.append(result)

        summary = issue_details.get("summary") or ""
        description = issue_details.get("description") or ""

        candidates.append({
            "key": candidate_key,
            "content": f"{summary}\n{description}".strip(),
        })

    if not candidates:
        return []
    
    # Build valid XML safely.
    request_root = ET.Element("comparison_request")

    primary_element = ET.SubElement(
        request_root,
        "primary_ticket",
        {"key": primary_issue_key},
    )
    primary_element.text = str(primary_issue_data)

    candidates_element = ET.SubElement(
        request_root,
        "candidates",
    )

    for candidate in candidates:
        candidate_element = ET.SubElement(
            candidates_element,
            "candidate",
            {"key": candidate["key"]},
        )
        candidate_element.text = candidate["content"]

    request_xml = ET.tostring(
        request_root,
        encoding="unicode",
    )

    prompt = f"""
Compare the primary Jira ticket with every candidate independently.

Return XML only using this exact structure:

<results>
  <match>
    <thought>Concise reason for the decision</thought>
    <related>true</related>
    <relationship>Relates</relationship>
    <source>SCRUM-1</source>
    <target>SCRUM-2</target>
  </match>
</results>

Requirements:
- Return one <match> for every candidate.
- Use only candidate keys provided in the input.
- related must be true or false.
- Do not include Markdown or text outside <results>.

{request_xml}
"""

    # Only one LLM call for every candidate.
    llm_result = linking_model.generator(prompt)
    try:
        results_root = ET.fromstring(llm_result.strip())
    except ET.ParseError as error:
        raise ValueError(
            f"Linking model returned invalid XML: {error}. "
            f"Output: {llm_result}"
        ) from error

    allowed_keys = {
        candidate["key"]
        for candidate in candidates
    }

    related_issues = []

    for match in results_root.findall("match"):
        target = (match.findtext("target") or "").strip()
        related_value = (
            match.findtext("related") or "false"
        ).strip().lower()
        relationship = (
            match.findtext("relationship") or ""
        ).strip().lower()
        thought = (
            match.findtext("thought") or ""
        ).strip()

        # Prevent the model from inventing Jira keys.
        if target not in allowed_keys:
            continue

        if related_value == "true":
            related_issues.append({
                "source": primary_issue_key,
                "target": target,
                "related": related_value == "true",
                "relationship": relationship,
                "thought": thought,
            })

    return related_issues

def generate_triage(ticket_key: str) -> dict:
    """Generate user stories, acceptance criteria, priority, reasoning, and a Jira comment for a ticket key."""
    primary_issue_key, primary_issue_data = asyncio.run(get_issue_by_id(ticket_key))
    llm_result = product_model.generator(f"<description>{primary_issue_data}</description>")

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

def triage_ticket(ticket_key: str) -> dict:
    """Run the complete read-only triage workflow."""

    # primary_key, _ = asyncio.run(
    #     get_issue_by_id(ticket_key)
    # )

    related_tickets = search_related_issues(ticket_key)
    # print(f"triage output: {related_tickets}")
    product_output = generate_triage(ticket_key)

    lines = [
        f"Triage complete for {ticket_key}",
        "",
    ]

    if related_tickets:
        lines.append("Related tickets found:")

        for item in related_tickets:
            relationship = item.get("relationship").title()
            lines.extend([
                f"- {item['source']} [{relationship}] {item['target']}",
                "Reason",
                item.get("thought", ""),
                "",
            ])
    else:
        lines.extend([
            "No related tickets found.",
            "The LLM checked open tickets but found no related issues.",
            "",
        ])

    lines.extend([
        "Generated Jira comment:",
        product_output["comment"],
    ])

    # print("\n".join(lines))
    return {
        "ticket_key": ticket_key,
        # "related_tickets": related_tickets,
        # "product_output": product_output,
        "message": "\n".join(lines),
    }

def jira_add_issue_comment(ticket_key: str, comment: str) -> dict:
    """Add a comment to a Jira issue."""
    result = asyncio.run(add_issue_comment(ticket_key, comment))
    return result

def draft_issue(user_request: str):
    llm_output = create_issue_model.generator(f"<description>{user_request}</description>")

    summary     = extract_tag(llm_output, "summary") or ''
    description = extract_tag(llm_output, "description") or ''
    work_type   = extract_tag(llm_output, "work_type") or ''
    
    draft = {
        "type": "draft_issue",
        "project_key": os.getenv("PROJECT_KEY"),
        "summary": summary,
        "description": description,
        "work_type": work_type,
    }

    required_fields = [
        "summary",
        "description",
        "work_type",
    ]

    missing_fields = [
        field
        for field in required_fields
        if not draft.get(field)
    ]

    if missing_fields:
        raise ValueError(
            f"Draft is missing required fields: {', '.join(missing_fields)}. "
            f"LLM output: {llm_output}"
        )

    allowed_work_types = {
        "Epic",
        "Setup Jira MCP Server",
        "Story",
        "Feature",
        "Request",
        "Bug",
    }

    if work_type not in allowed_work_types:
        raise ValueError(
            f"Invalid work type '{work_type}'. "
            f"Allowed values: {', '.join(sorted(allowed_work_types))}"
        )

    return draft

# Put all tool functions into a dictionary for easy subsequent calling
available_tools = {
    "get_issue_detail": {
        "function": get_issue_detail,
        "description": "Fetch one Jira issue by key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "Jira ticket key, for example SCRUM-5."
                }
            },
            "required": ["ticket_key"]
        }
    },

    "search_jira_tickets": {
        "function": search_jira_tickets,
        "description": "Search Jira tickets by project key, status, and assignee. Returns count and ticket details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_key": {"type": "string", "description": "Project key, for example SCRUM or AAT."},
                "status": {"type": "string", "description": "Status, for example To Do, In Progress, Done."},
                "assignee": {"type": "string", "description": "Assignee name, or me/currentUser."},
                "max_results": {"type": "string", "description": "Maximum number of tickets to return."},
            },
            "required": [],
        },
    },

    "count_jira_tickets": {
        "function": count_jira_tickets,
        "description": "Count Jira tickets by project key, status, and assignee.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_key": {"type": "string", "description": "Project key, for example SCRUM or AAT."},
                "status": {"type": "string", "description": "Status, for example To Do, In Progress, Done."},
                "assignee": {"type": "string", "description": "Assignee name, or me/currentUser."},
            },
            "required": [],
        },
    },

    "search_related_issues": {
        "function": search_related_issues,
        "description": "Find open Jira issues related to a given ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "Jira ticket key to compare with other open issues."
                }
            },
            "required": ["ticket_key"]
        }
    },

    "triage_ticket": {
        "function": triage_ticket,
        "description": (
            "Run the complete read-only Jira triage workflow. "
                # "Fetch the ticket, find related open tickets, and generate "
                # "user stories, acceptance criteria, priority, reasoning, "
                # "and a proposed Jira comment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "Jira ticket key, for example SCRUM-5."
                }
            },
            "required": ["ticket_key"]
        }
    },

    "draft_issue": {
        "function": draft_issue,
        "description": "Draft a new Jira issue from the user's request. Does not create it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_request": {
                    "type": "string",
                    "description": "The user's request, for example: create a bug for database connection failed."
                }
            },
            "required": ["user_request"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["create_issue"]},
                "project_key": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "work_type": {
                    "type": "string",
                    "enum": ["Bug", "Task", "Story", "Epic", "Setup Jira MCP Server", "Feature", "Request"]
                }
            },
            "required": [
                "type",
                "project_key",
                "summary",
                "description",
                "work_type"
            ]
        }
    },

    "jira_add_issue_comment": {
        "function": jira_add_issue_comment,
        "description": "Draft a comment to a Jira issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_key": {
                    "type": "string",
                    "description": "Jira ticket key to add a comment to."
                },
                "comment": {
                    "type": "string",
                    "description": "The comment text to add to the Jira issue."
                }
            },
            "required": ["ticket_key", "comment"]
        }
    },

    "run_jira_toolkit": {
        "function": run_jira_toolkit,
        "description": "Fallback: use LangChain JiraToolkit for general Jira questions not covered by custom tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_request": {"type": "string", "description": "Natural language Jira request."}
            },
            "required": ["user_request"],
        },
    },
}

formatted_system_prompt = system_prompts["agent_system_prompt"].format(
    available_tools=format_available_tools(available_tools)
)
reAct_agent_model.base_messages[0]["content"] = formatted_system_prompt

# ----------------------------
# LangGraph Nodes
# ----------------------------
def reasoning_node(state: AgentState) -> AgentState:
    
    full_prompt = "\n".join(state["hist_messages"])
    llm_output = reAct_agent_model.generator(f"{state['user_request']}\n\n{full_prompt}")
    print(f"LLM Output:\n{llm_output}\n")

    # Truncate extra Thought-Action pairs that the model may generate
    # to ensure we only process the first one.
    match = re.search(r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)', 
                    llm_output, re.DOTALL)
    if match: # if more than one Thought-Action pair is found, truncate to the first one
        truncated = match.group(1).strip()
        if truncated != llm_output.strip():
            llm_output = truncated
            print("Truncated extra Thought-Action pairs")

    action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
    if action_match:
        action_str = action_match.group(1).strip()

        if action_str.startswith("Finish"):
            finish_match = re.match(r"Finish\[(.*)\]", action_str, re.DOTALL)

            final_answer = "Error: Finish action found but no answer provided."
            if finish_match:
                final_answer = finish_match.group(1).strip()

            return {    
                "hist_messages": [llm_output],
                "final_answer": final_answer,
                "next_action": "finish",
                "iterations": state["iterations"] + 1,
            }

    return {
        "hist_messages": [llm_output],
        "next_action": "action"    
        }

def action_node(state: AgentState) -> AgentState:
    last_message = state["hist_messages"][-1]
    action_match = re.search(r"Action:\s*(.*)", last_message, re.DOTALL)

    # validation: if no action is found, return an error observation
    if not action_match:
        observation = "Error: No action found. Please explicitly use Action: finish(...) or other actions."
        observation_str = f"Observation: {observation}"
        return {
            "hist_messages": [observation_str],
            "next_action": "reasonings",  # always route back through reasoning next
            "iterations": state["iterations"] + 1,
        }
    
    action_str = action_match.group(1).strip()
    tool_name = re.search(r"(\w+)\(", action_str).group(1)
    args_match = re.search(r"\((.*)\)", action_str, re.DOTALL).group(1)
    kwargs = dict(re.findall(r'(\w+)="([^"]*)"', args_match)) if args_match else {}
    
    # draft = None
    if tool_name in available_tools:
        try:
            tool_func = available_tools[tool_name]["function"]
            observation = tool_func(**kwargs)

            # if tool_name == "draft_issue":
            #     if isinstance(observation, dict):
            #         draft = observation
            #     else:
            #         observation = (
            #             "Error: draft_issue must return a dictionary."
            #         )

        except Exception as e:
            observation = f"Error executing {tool_name}: {e}"
    else:
        observation = f"Error: Undefined tool '{tool_name}'"
        
    observation_str = f"Observation: {observation}"
    print(observation_str)
    state_update = {
        "hist_messages": [observation_str],
        "next_action": "reasoning",             # always route back through reasoning next
        "iterations": state["iterations"] + 1,
        "draft": observation,
    }

    # Only update the draft state when draft_issue returned a dictionary.
    # if draft is not None:
    #     state_update["draft"] = draft

    return state_update

def reasoning_router(state: AgentState) -> str:
    if state["next_action"] == "finish" or state["iterations"] >= MAX_ITERATIONS:
        return "end"
    return "action"

def _build_langGraph():
    graph = StateGraph(AgentState)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("action", action_node)

    graph.set_entry_point("reasoning")
    graph.add_conditional_edges("reasoning", reasoning_router, {"action": "action", "end": END})
    graph.add_edge("action", "reasoning")

    return graph.compile()

def invoke(user_input: str) -> str:
    app = _build_langGraph()
    initial_state: AgentState = {
        "user_request": user_input,
        "hist_messages": [],
        "next_action": "",
        "final_answer": "",
        "iterations": 0,
    }

    result = app.invoke(initial_state)
    output = result.get("final_answer")
    # print(f"final output: {result.get("last_tool_result")}")
    
    message = result.get("hist_messages", [])[-3]
    tool_name = re.search(r"Action:\s*([A-Za-z_]\w*)\s*\(",message,).group(1)

    if tool_name == "triage_ticket":
        tool_result = result.get("draft")
        tool_result = tool_result.get("message", "")
        output = f"{result.get("final_answer")}\n\n{tool_result}".strip()
        
    if not output:
        thought_message = result.get("hist_messages")[-1]
        output = re.match(r"Thought: *(.*?)(?=Action:)", thought_message, re.DOTALL).group(1).strip()

    return {
        "function": tool_name,
        "output": output,
        "agent_trace": result.get("hist_messages", []),
        "details": result,
        "draft": result.get("draft"),
        # "last_tool_result": result.get("observation")
    }


if __name__ == "__main__":
    user_request = "triage SCRUM-7"
    final_answer = invoke(user_request)
    # print(f"Final Answer: {final_answer}")