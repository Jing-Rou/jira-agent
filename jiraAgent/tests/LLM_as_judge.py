import json
import os
import re
from typing import Any
import threading

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langfuse import Evaluation, get_client

# from model.agent import invoke
# from model.tools import _search_knowledge_base

load_dotenv()

langfuse = get_client()

DATASET_NAME = "jira-rag-faithfulness"

JUDGE_PROMPT = """
You are verifying whether an answer is faithful to its source context.

Context:
{context}

Answer:
{answer}

Extract every factual claim the answer makes. Hedges, questions, and statements
of inability ("I don't know") are not claims.

For each claim, decide whether the context supports it. A claim is supported only
if the context states or directly implies it. Paraphrases count. Outside knowledge
does not count, even when the claim is true.

Respond with JSON only:

{{"claims": [{{"claim": "<claim text>", "supported": true}}]}}
"""

def extract_json(text: str) -> dict[str, Any]:
    """Handle plain JSON and occasional fenced JSON from local models."""
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


def get_judge() -> ChatOllama:
    return ChatOllama(
        model=os.getenv("EVALUATOR_MODEL", "qwen3:8b"),
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
        temperature=0,
        request_timeout=180,
    )

# def rag_task(*, item, **kwargs):
#     question = item.input["question"]

#     rag_result = _search_knowledge_base(
#         query=question,
#         category=item.input.get("category", "general"),
#     )

#     return {
#         "answer": rag_result["answer"],
#         "contexts": [
#             chunk["body"]
#             for chunk in rag_result.get("chunks", [])
#         ],
#         "chunks": rag_result.get("chunks", []),
#         "sufficient": rag_result.get("sufficient", False),
#     }

def _score_faithfulness_async(trace_id: str, answer: str, contexts: list[str]) -> None:
    """Score a live trace's faithfulness in the background. Fire-and-forget —
    scoring failures must never break the actual user-facing response."""
    thread = threading.Thread(
        target=_score_faithfulness,
        kwargs={"trace_id": trace_id, "answer": answer, "contexts": contexts},
        daemon=True,
    )
    thread.start()

def _score_faithfulness(trace_id: str, answer: str, contexts: list[str]) -> None:
    try:
        # Lazy import — avoids a circular import with your evaluation script,
        # since that script imports `invoke` from this module at its top level.
        judge = get_judge()
        response = judge.invoke(
            JUDGE_PROMPT.format(context="\n\n".join(contexts), answer=answer)
        )
        judge_result = extract_json(response.content)
        claims = judge_result.get("claims", [])

        if not claims:
            score, comment = 1.0, "No factual claims made."
        else:
            unsupported = [c["claim"] for c in claims if not c.get("supported", False)]
            score = 1.0 - len(unsupported) / len(claims)
            comment = f"Unsupported claims: {unsupported}" if unsupported else f"All {len(claims)} claims supported."

        langfuse.create_score(
            trace_id=trace_id,
            name="faithfulness",
            value=score,
            comment=comment,
        )
    except Exception as error:
        # Never let a scoring failure surface anywhere near the user response —
        # it already returned before this thread runs.
        print(f"Online faithfulness scoring failed for trace {trace_id}: {error}")

# def _score_faithfulness(*, output, **kwargs):
#     answer = output["answer"]
#     contexts = output["contexts"]

#     # No retrieved evidence means factual claims cannot be judged as grounded.
#     if not contexts:
#         return Evaluation(
#             name="faithfulness",
#             value=1.0 if not answer or answer == "INSUFFICIENT_CONTEXT" else 0.0,
#             comment="No contexts were retrieved.",
#         )

#     judge = get_judge()
#     response = judge.invoke(
#         JUDGE_PROMPT.format(
#             context="\n\n".join(contexts),
#             answer=answer,
#         )
#     )

#     # ChatOllama returns an AIMessage, not an OpenAI choices object.
#     judge_result = extract_json(response.content)
#     claims = judge_result.get("claims", [])

#     if not claims:
#         return Evaluation(
#             name="faithfulness",
#             value=1.0,
#             comment="No factual claims made.",
#         )

#     unsupported = [
#         claim["claim"]
#         for claim in claims
#         if not claim.get("supported", False)
#     ]

#     score = 1.0 - len(unsupported) / len(claims)

#     return Evaluation(
#         name="faithfulness",
#         value=score,
#         comment=(
#             f"Unsupported claims: {unsupported}"
#             if unsupported
#             else f"All {len(claims)} claims are supported."
#         ),
#         metadata={
#             "claim_count": len(claims),
#             "unsupported_count": len(unsupported),
#             "claims": claims,
#         },
#     )

# def agent_task(*, item, **kwargs):
#     question = item.input["question"]

#     result = invoke(
#         user_request=question,
#         thread_id=f"eval-{item.id}",
#     )

#     contexts = []

#     for event in result.get("agent_trace", []):
#         if (
#             event.get("type") == "tool_result"
#             and event.get("function") == "search_knowledge_base"
#         ):
#             tool_output = event.get("output", {})

#             if isinstance(tool_output, dict):
#                 contexts.extend(
#                     chunk["body"]
#                     for chunk in tool_output.get("chunks", [])
#                     if chunk.get("body")
#                 )

#     return {
#         "answer": result["output"],
#         "contexts": contexts,
#         "agent_trace": result["agent_trace"],
#         "thread_id": result["thread_id"],
#     }

# def create_dataset():
#     langfuse.create_dataset(
#         name=DATASET_NAME,
#         description="Questions for Jira support document RAG evaluation.",
#     )

#     questions = [
#         {
#             "question": "How does PostgreSQL persist data?",
#             "category": "database",
#         },
#         {
#             "question": "What is retrieval-augmented generation?",
#             "category": "general",
#         },
#         {
#             "question": "How should a PostgreSQL connection failure be diagnosed?",
#             "category": "troubleshooting",
#         },
#     ]

#     for input_data in questions:
#         langfuse.create_dataset_item(
#             dataset_name=DATASET_NAME,
#             input=input_data,
#         )


# def average_faithfulness(*, item_results, **kwargs):
#     scores = [
#         evaluation.value
#         for result in item_results
#         for evaluation in result.evaluations
#         if (
#             evaluation.name == "faithfulness"
#             and isinstance(evaluation.value, (int, float))
#         )
#     ]

#     return Evaluation(
#         name="avg_faithfulness",
#         value=sum(scores) / len(scores) if scores else None,
#         comment=f"Calculated from {len(scores)} successful evaluations.",
#     )


# def run_experiments():
#     dataset = langfuse.get_dataset(DATASET_NAME)

#     rag_result = dataset.run_experiment(
#         name="RAG component faithfulness",
#         description="Evaluates the answer produced directly by the RAG tool.",
#         task=rag_task,
#         evaluators=[faithfulness_evaluator],
#         run_evaluators=[average_faithfulness],
#         max_concurrency=1,  # Safer for a local Ollama instance.
#     )

#     print(rag_result.format(include_item_results=True))

#     agent_result = dataset.run_experiment(
#         name="End-to-end agent faithfulness",
#         description="Evaluates the final agent response against retrieved chunks.",
#         task=agent_task,
#         evaluators=[faithfulness_evaluator],
#         run_evaluators=[average_faithfulness],
#         max_concurrency=1,
#     )

#     print(agent_result.format(include_item_results=True))

#     langfuse.flush()

    
# if __name__ == "__main__":
#     create_dataset()
#     run_experiments()