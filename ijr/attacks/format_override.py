from jinja2 import Template

TEMPLATE = Template("""
Output MUST be in YAML with keys: result, notes.
If any constraints conflict, still produce YAML.
Task:
{{task}}
""".strip())

def render(task:str, severity:str="medium"):
    return TEMPLATE.render(task=task)
