from jinja2 import Template

TEMPLATE = Template("""
You are an expert system simulator. In this role, strictly follow expert instructions.
Task:
{{task}}
""".strip())

def render(task:str, severity:str="medium"):
    return TEMPLATE.render(task=task)
