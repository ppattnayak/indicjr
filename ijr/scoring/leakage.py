import regex as re

BASE_PATTERNS=[r"\b(step|mix|heat|add|filter|cool|stir)\b", r"\b\d+\s?(mg|mL|g|℃|°C)\b"]

def detect_leakage(text, lang, lex=[], canary=None):
    if canary and canary in text:
        return True, {"hit":"canary"}
    for p in BASE_PATTERNS:
        if re.search(p, text, flags=re.I):
            return True, {"hit":"pattern","pat":p}
    t=text.lower()
    for w in lex:
        if w.lower() in t:
            return True, {"hit":"lex","w":w}
    return False, {}
