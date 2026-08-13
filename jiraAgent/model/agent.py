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
from langgraph.checkpoint.postgres import PostgresSaver
from model.tools import TOOLS

from langfuse import get_client, propagate_attributes
from langfuse.langchain import CallbackHandler
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from tests.LLM_as_judge import _score_faithfulness_async

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
        model=os.getenv("LLM_MODEL", "qwen3:8b"),
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
        temperature=0,
        request_timeout=300.0,
    )

    # Define system prompt
    default_system_prompt = "You are a helpful AI assistant, please respond to the user's query to the best of your ability! Execute a tool call whenever you see fit."

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

    # NEW — online evaluation: score THIS live trace, not a batch dataset
    if contexts and trace_id:
        _score_faithfulness_async(trace_id=trace_id, answer=final_output, contexts=contexts)


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
