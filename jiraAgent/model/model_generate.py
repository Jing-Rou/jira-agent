import os
import re
import json
import asyncio
from wsgiref import headers
import requests
import concurrent.futures

from typing                                     import Union
from jiraToolWrapper.tools.get_unsolved_ticket  import get_unsolved_ticket
from jiraToolWrapper.tools.create_issue_link    import create_issue_link
from jiraToolWrapper.tools.add_issue_comment    import add_issue_comment
from jiraToolWrapper.tools.get_issue_by_id      import get_issue_by_id
from jiraToolWrapper.tools.create_issue         import create_issue
from model.system_prompts                       import PROMPTS as system_prompts

from dotenv import load_dotenv
load_dotenv()

class LLM_Model():
    def __init__(self, 
                 system_key: str, 
                 examples_key: str):
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL")
        self.system_key = system_key
        self.examples_key = examples_key

        # Load examples once
        with open("model/prompts.json", "r") as f:
            self.example_prompts = json.load(f)

        # system prompt
        self.base_messages = [
            {
                "role": "system", 
                "content": system_prompts[self.system_key]
            }
        ]
        
        for prompt in self.example_prompts[self.examples_key]:
            self.base_messages  .extend(
                [
                    {"role": "user", "content": prompt["input"]},
                    {"role": "assistant", "content": prompt["output"]}
                ]
            )


    def generator(self, user_input: str) -> str:
        messages = self.base_messages.copy()
        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.2,
            },
        }

        headers = {}

        if api_key := os.getenv("OLLAMA_API_KEY"):
            headers["Authorization"] = f"Bearer {api_key}"

        # send out the HTTP POST request with streaming enabled
        response = requests.post(
            f"{self.base_url}/api/chat", 
            json=payload, 
            timeout=120,
            headers=headers
            )

        response.raise_for_status()
        result = response.json()        

        return result["message"]["content"]

create_issue_model   = LLM_Model(system_key="system_prompt_create_issue",   examples_key="examples_create_issue")
product_model        = LLM_Model(system_key="system_prompt_product",        examples_key="examples_product")
linking_model        = LLM_Model(system_key="system_prompt_linking",        examples_key="examples_linking")

# ----------------------------------------------------------------
# Tag extractor - fixed closing tag regex
# ----------------------------------------------------------------
def extract_tag(text: str, tag: str = "related") -> Union[str, None]:
    try:
        if match := re.compile(
            f"<{tag}>(.*?)</{tag}>", flags=re.DOTALL  # fixed: was <tag>...<tag>
        ).search(text):
            return match.group(1).strip()
    except Exception as e:
        print(f"ERROR extract_tag: {e}")        
    
def check_issue_and_link_helper(args):
    key, data, primary_issue_key, primary_issue_data = args

    if key == primary_issue_key:
        return None

    result = llm_check_ticket_match(primary_issue_data, data, primary_issue_key, key)

    if result["related"]:
        asyncio.run(create_issue_link(primary_issue_key, key))

    return result

def find_related_tickets(primary_issue_key, primary_issue_data, issues):
    args = [(key, data, primary_issue_key, primary_issue_data) for key, data in issues.items()]
    with concurrent.futures.ThreadPoolExecutor(os.cpu_count()) as executor:
        results = list(executor.map(check_issue_and_link_helper, args))

    return [result for result in results if result]

def llm_check_ticket_match(ticket1, ticket2, key1, key2):
    llm_result = linking_model.generator(
        f"<ticket1>{ticket1}</ticket1><ticket2>{ticket2}</ticket2>"
    )

    related_value = extract_tag(llm_result) or "False"
    thought = extract_tag(llm_result, "thought") or ""
    # convert string to actual boolean
    is_related = related_value.strip().lower() == "true"

    return {
        "source": key1,
        "target": key2,
        "related": is_related,
        "thought": thought,
        "llm_output": llm_result,
    }

def user_stories_acceptance_criteria_priority(primary_issue_key, primary_issue_data):
    if llm_result := product_model.generator(f"<description>{primary_issue_data}</description>"):
        user_stories = extract_tag(llm_result,"user_stories") or ''
        acceptance_criteria = extract_tag(llm_result, "acceptance_criteria") or ''
        priority = extract_tag(llm_result,"priority") or ''
        thought = extract_tag(llm_result,"thought") or ''
        comment = f"user_stories: {user_stories}\nacceptance_criteria: {acceptance_criteria}\npriority: {priority}\nthought: {thought}"
        asyncio.run(add_issue_comment(primary_issue_key, comment))
        return {
            "comment": comment,
            "llm_output": llm_result,
        }

    return {
        "comment": "No product output generated.",
        "llm_output": "",
    }

def draft_issue(user_request: str):
    result = create_issue_model.generator(
        f"<description>{user_request}</description>"
    )

    summary     = extract_tag(result, "summary") or ''
    description = extract_tag(result, "description") or ''
    work_type   = extract_tag(result, "work_type") or ''
    
    return {
        "summary": summary,
        "description": description,
        "work_type": work_type
    }

def confirmed_create_issue(summary, description, work_type):
    # actually create the ticket in Jira
    created = asyncio.run(
        create_issue(summary, description, work_type)
    )
    ticket_key = created.get("key")

    return ticket_key

def triage(ticket_number: str) -> dict:
    """triage a given ticket and link related tickets"""
    ticket_number = str(ticket_number)
    all_tickets = asyncio.run(get_unsolved_ticket())
    primary_issue_key, primary_issue_data = asyncio.run(get_issue_by_id(ticket_number))
    link_checks = find_related_tickets(primary_issue_key, primary_issue_data, all_tickets)
    related_tickets = [check for check in link_checks if check["related"]]
    product_output = user_stories_acceptance_criteria_priority(primary_issue_key, primary_issue_data)

    lines = [
        f"Triage complete for {primary_issue_key}",
        "",
    ]

    if related_tickets:
        lines.append("Related tickets found:")
        for item in related_tickets:
            lines.extend([
                f"- {item['source']} relates to {item['target']}",
                "  LLM output:",
                item["thought"],
                "",
            ])
    else:
        lines.extend([
            "No related tickets found.",
            "The LLM checked the open tickets but did not mark any as related.",
            "",
        ])

    lines.extend([
        "Generated Jira comment:",
        product_output["comment"],
    ])

    return {
        "ticket_key": primary_issue_key,
        "related_tickets": related_tickets,
        "checks": link_checks,
        "product_output": product_output,
        "message": "\n".join(lines),
    }

if __name__ == "__main__":
    pass