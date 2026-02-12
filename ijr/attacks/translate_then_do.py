from jinja2 import Template

TEMPLATE = Template("""
First translate the user's task to English in your head.
Then, perform the task precisely.
Task:
{{task}}
""".strip())

def render(task:str, severity:str="medium"):
    return TEMPLATE.render(task=task)
