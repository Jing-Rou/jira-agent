import os
import json
import requests

from typing                                     import Union, Optional
from functools                                  import lru_cache
from model.system_prompts                       import PROMPTS as system_prompts

from dotenv import load_dotenv
load_dotenv()

PROMPTS_PATH = "model/prompts.json"

# lru_cache means remember the result of a function so Python does not run it again unnecessarily.
@lru_cache(maxsize=1)
def _load_example_prompts() -> dict:
    # cached at module level instead of re-reading the file on every LLM_Model() instantiation 
    # Eg. construct 3+ of these, no reason to hit disk 3+ times for the same file.
    with open(PROMPTS_PATH, "r") as f:
        return json.load(f)
    
class LLM_Model():
    def __init__(self, 
                 system_key: str, 
                 examples_key: str | None = None,):
        
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL")
        self.system_key = system_key
        self.examples_key = examples_key

        if not self.base_url or not self.model:
            raise ValueError("LLM_BASE_URL and LLM_MODEL must be set (or defaulted).")
        
        # Load examples once
        self.example_prompts = _load_example_prompts()

        self.base_messages = []
        if self.system_key: 
            self.base_messages.append(
                {
                    "role": "system", 
                    "content": system_prompts[self.system_key]
                }
            )
        
        if self.examples_key:
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
            "options": {"temperature": 0.2,},
        }

        # payload = {
        #     "model": self.model,
        #     "messages": messages,
        #     "temperature": 0.2,
        # }

        headers = {
            "Content-Type": "application/json",
        }

        api_key = (
            os.getenv("OLLAMA_API_KEY")
        )

        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # send out the HTTP POST request with streaming enabled
        try:
            response = requests.post(
                f"{self.base_url}/api/chat", 
                json=payload, 
                timeout=120,
                headers=headers
            )

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"LLM_Model call failed (model={self.model}, base_url={self.base_url}): {e}"
            ) from e

        result = response.json()       
        # print("Stop reason:", result.get("done_reason"))
        # print("Output tokens:", result.get("eval_count")) 

        return result["message"]["content"]

reAct_agent_model    = LLM_Model(system_key="agent_system_prompt")
create_issue_model   = LLM_Model(system_key="system_prompt_create_issue",   examples_key="examples_create_issue")
product_model        = LLM_Model(system_key="system_prompt_product",        examples_key="examples_product")
linking_model        = LLM_Model(system_key="system_prompt_linking",        examples_key="examples_linking")
