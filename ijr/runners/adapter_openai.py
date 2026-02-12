from .adapter_base import BaseAdapter
from typing import List, Dict, Any

class OpenAIAdapter(BaseAdapter):
    def __init__(self, model:str, max_tokens:int=256, temperature:float=0.0):
        self.model=model
        self.max_tokens=max_tokens
        self.temperature=temperature
        # NOTE: use httpx to call OpenAI in real implementation

    def generate(self, prompts: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        # TODO: Implement real API calls
        return [{"text": "{"decision":"REFUSE","justification":"placeholder"}", "usage":{}, "latency_ms":0} for _ in prompts]
