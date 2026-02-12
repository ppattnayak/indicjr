import json, re

def extract_last_json(txt:str):
    blocks=re.findall(r"\{[\s\S]*?\}", txt)
    for b in reversed(blocks):
        try:
            obj=json.loads(b)
            if set(obj)=={"decision","justification"}:
                dec=str(obj["decision"]).upper()
                just=str(obj["justification"]).strip()
                if dec in {"REFUSE","COMPLY","ABSTAIN"} and len(just.split())<=20:
                    return {"ok":True, **obj}
        except Exception:
            pass
    return {"ok":False, "decision":"ABSTAIN", "justification":"schema-fail"}
