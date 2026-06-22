import json
import requests

from dataclasses import dataclass
from model.system_prompts import PROMPTS as system_prompts
I
from langchain.tools import tool

@dataclass
class LLM_Model():
    
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def construct_prompt(self, user_input: str) -> list[dict]:
        with open("model/prompts.json") as f:
            example_prompts = json.load(f)

        few_short_prompt = []

        # system prompt
        few_short_prompt = [{"role": "system", "content": system_prompts}]
        for prompt in example_prompts:
            few_short_prompt.append(
                [{"role": "user", "content": prompt["input"]},
                 {"role": "assistant", "content": prompt["output"]}
                ]
            )

        few_short_prompt.append({"role": "user", "content": f"<description>{user_input}</description>"})
        
        return few_short_prompt

    def generator(self, user_input: str) -> str:

        payload = {
            "model": self.model,
            "messages": self.construct_prompt(user_input),
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        # send out the HTTP POST request with streaming enabled
        response = requests.post(
            f"{self.base_url}/api/chat", 
            json=payload, 
            timeout=120,
            )

        response.raise_for_status()
        data = response     .json()
        
        return data["message"]["content"]
    
    def check_issue_and_link_helper(args):
        key, data, primary_issue_key, primary_issue_data = args
        if key != primary_issue_key and \
        llm_check_ticket_match(primary_issue_data, data):
            jira_utils.link_jira_issue(primary_issue_key, key) 

    def find_related_tickets(primary_issue_key, primary_issue_data, issues):
        args = [(key, data, primary_issue_key, primary_issue_data) for key, data in issues.items()]
        with concurrent.futures.ThreadPoolExecutor(os.cpu_count()) as executor:
            executor.map(check_issue_and_link_helper, args)

    def llm_check_ticket_match(ticket1, ticket2):
        llm_result = linking_model.run_llm(f"<ticket1>{ticket1}<ticket1><ticket2>{ticket2}<ticket2>")
        if ((result := jira_utils.extract_tag_helper(llm_result))) \
        and (result == 'True'):
            return True 
        
    def user_stories_acceptance_criteria_priority(primary_issue_key, primary_issue_data):
        if llm_result := product_model.run_llm(f"<description>{primary_issue_data}<description>"):
            print(f"llm_result: {llm_result}")
            user_stories = jira_utils.extract_tag_helper(llm_result,"user_stories") or ''
            acceptance_criteria = jira_utils.extract_tag_helper(llm_result,"acceptance_criteria") or ''
            priority = jira_utils.extract_tag_helper(llm_result,"priority") or ''
            thought = jira_utils.extract_tag_helper(llm_result,"thought") or ''
            comment = f"user_stories: {user_stories}\nacceptance_criteria: {acceptance_criteria}\npriority: {priority}\nthought: {thought}"
            jira_utils.add_jira_comment(primary_issue_key, comment) 

    @tool
    def triage(ticket_number:str) -> str:
        """triage a given ticket and link related tickets"""
        ticket_number = str(ticket_number)
        all_tickets = jira_utils.get_all_tickets()
        primary_issue_key, primary_issue_data = jira_utils.get_ticket_data(ticket_number)
        find_related_tickets(primary_issue_key, primary_issue_data, all_tickets)
        user_stories_acceptance_criteria_priority(primary_issue_key, primary_issue_data)
        return "Task complete"


# if __name__ == "__main__":
    

#     client = LLM_Model(base_url="http://localhost:11434", model="llama3.2")
#     client.generator(request)