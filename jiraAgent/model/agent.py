import os
import traceback
import json

from typing import Callable
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from model.tools import TOOLS

from langfuse import get_client, propagate_attributes
from langfuse.langchain import CallbackHandler
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

from dotenv import load_dotenv
load_dotenv()

# Trace internal LlamaIndex retrieval and synthesis operations.
LlamaIndexInstrumentor().instrument()

langfuse = get_client()
langfuse_handler = CallbackHandler()

def get_graph_closure() -> Callable:
    """Graph generator closure."""

    # document_count = initialize_documents()
    # print(f"Knowledge base ready: {document_count} PDF chunks loaded")

    # Initialise ChatWatsonx
    llm_model = ChatOllama(
        model=os.getenv("LLM_MODEL"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0,
        request_timeout=300.0,
    )

    # Define system prompt
    default_system_prompt = """
    You are a Jira support assistant. Use only tool results from this conversation.

    TOOL ROUTING
    - If a request contains a Jira ticket key (for example, SCRUM-32), call
    `get_issue_detail` for that exact key.
    - If a request asks for a solution, implementation guidance, documents,
    knowledge base, or RAG, call `search_knowledge_base`.
    - If a request needs both Jira details and knowledge-base guidance:
    1. Call `get_issue_detail` first.
    2. Use the returned issue summary and description to create the KB query.
    3. Call `search_knowledge_base`.
    4. Do not produce a final answer until both tool results are available.
    - For a knowledge-base-only request, always call `search_knowledge_base`.
    - Do not call Jira tools for a document-only request.
    - Do not create a Jira issue unless the current user message explicitly asks
    to create one.

    GROUNDING
    - Use Jira tool results only for Jira facts.
    - Use KB tool results only for implementation guidance.
    - Never use general knowledge, guess, or add unsupported advice.
    - Never expose tool names, function calls, code, raw chunks, scores, JSON,
    evaluation results, verdicts, or internal workflow.

    FINAL ANSWER
    - For combined Jira + KB requests, return these sections in this order:

    ## Issue details
    Include the Jira key, summary, description, and status only when returned.

    ## Implementation guidance
    List only guidance supported by relevant KB results.

    - Do not replace Jira details with KB content.
    - Do not merge the two sections into one summary.
    - For Jira-only requests, return only the Issue details section.
    - For KB-only requests, return only the Implementation guidance section.

    FALLBACKS
    - If Jira returns no accessible issue, reply exactly:
    "I cannot answer this based on the available Jira data."
    - If `search_knowledge_base` returns no relevant result, reply exactly:
    "No related knowledge-base guidance was found."
    - If both sources are required and KB has no relevant result, show the Issue
    details section first, then write:
    "No related knowledge-base guidance was found."
    """
    # Initialise memory saver
    memory = MemorySaver()
    # The checkpointer stores the graph state for every thread_id.
    # checkpointer = _create_checkpointer()

    def get_graph(system_prompt=default_system_prompt) -> CompiledStateGraph:
        """Get compiled graph with overwritten system prompt, if provided"""
        graph = create_agent(
            llm_model, tools=TOOLS, checkpointer=memory, system_prompt=system_prompt
        )
        return graph

    return get_graph

def invoke_agent(
    graph: CompiledStateGraph,
    user_request: str,
    thread_id: str = "user-1",
):
    request_id = str(uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "callbacks": [
            langfuse_handler,
        ],
        "run_name": "jira-react-agent",
        "tags": ["jira", "langgraph", "react", "rag"],
        "metadata": {
            "request_id": request_id,
        },
        "recursion_limit": 10,
    }

    trace_id = None

    with langfuse.start_as_current_observation(
        as_type="agent",
        name="jira-agent-request",
        input={"request": user_request},
    ) as agent_span:
        trace_id = agent_span.trace_id 

        with propagate_attributes(
            user_id=thread_id,
            session_id=thread_id,
            tags=["jira", "langgraph", "react", "rag"],
            metadata={"request_id": request_id},
        ):
            try:
                result = graph.invoke(
                    {"messages": [{
                            "role": "user",
                            "content": user_request,
                        }]
                    },
                    config=config,
                )

                final_output = result["messages"][-1].content
                agent_span.update(output={"response": final_output})

                return result, trace_id

            except Exception as error:
                agent_span.update(
                    level="ERROR",
                    status_message=str(error),
                    metadata={
                        "exception_type": type(error).__name__,
                        "traceback": traceback.format_exc(),
                    },
                )
                raise

    return result

# Build the graph once when Django starts.
_graph_factory = get_graph_closure()
_graph = _graph_factory()

def _parse_tool_output(content):
    """Convert a tool result into a JSON-compatible value."""
    if not isinstance(content, str):
        return content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content

def invoke(user_request: str, thread_id: str | None = None) -> dict:
    """Django-compatible entry point for the Jira agent."""
    thread_id = thread_id or str(uuid4())

    result, trace_id  = invoke_agent(
        graph=_graph,
        user_request=user_request,
        thread_id=thread_id,
    )

    messages = result.get("messages", [])
    final_message = messages[-1] if messages else None
    final_output = getattr(final_message, "content", "")

    function_name = None
    draft = None
    triage = None
    agent_trace = []
    contexts = []

    for message in messages:
        print(f"Message: {message}")
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                function_name = tool_call.get("name")

                agent_trace.append({
                    "type": "tool_call",
                    "function": function_name,
                    "arguments": tool_call.get("args", {}),
                    "call_id": tool_call.get("id"),
                })

        elif isinstance(message, ToolMessage):
            tool_output = _parse_tool_output(message.content)
            print(f"Tool output: {tool_output}")
            agent_trace.append({
                "type": "tool_result",
                "function": message.name,
                "output": tool_output,
                "call_id": message.tool_call_id,
            })

            if message.name == "draft_issue" and isinstance(tool_output, dict):
                draft = tool_output

            if message.name == "generate_triage" and isinstance(tool_output, dict):
                triage = tool_output

            # NEW — same extraction pattern as agent_task() in the eval script
            if message.name == "search_knowledge_base" and isinstance(tool_output, dict):
                contexts.extend(
                    chunk["body"]
                    for chunk in tool_output.get("chunks", [])
                    if chunk.get("body")
                )

    # # NEW — online evaluation: score THIS live trace, not a batch dataset
    # if contexts and trace_id:
    #     _score_faithfulness_async(trace_id=trace_id, answer=final_output, contexts=contexts)
    print("FINAL MESSAGE:", final_message)
    print("FINAL OUTPUT:", final_output)

    return {
        "function": function_name,
        "output": final_output,
        "draft": draft,
        "triage": triage,
        "agent_trace": agent_trace,
        "details": {},
        "thread_id": thread_id,
    }

# def main():
#     graph_factory = get_graph_closure()
#     graph = graph_factory()

#     try:
#         result = invoke_agent(
#             graph,
#             "VPN failed to connect, please triage the issue and create a Jira ticket if necessary.",
#         )
#         print(result["messages"][-1].content)
#     finally:
#         # Needed for short-running scripts.
#         langfuse.flush()

# if __name__ == "__main__":
#     main()
