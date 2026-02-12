from typing import List, Dict, Any

class BaseAdapter:
    def generate(self, prompts: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        raise NotImplementedError
