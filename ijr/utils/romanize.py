from ai4bharat.transliteration import XlitEngine
XLIT = {}

def to_roman(text:str, lang:str)->str:
    if lang not in XLIT:
        XLIT[lang]=XlitEngine(lang)
    return XLIT[lang].transliterate(text, target_script="latin")

def mix_scripts(text:str, lang:str, p=0.4):
    import random
    toks=text.split()
    for i,t in enumerate(toks):
        if random.random()<p:
            toks[i]=to_roman(t, lang)
    return ' '.join(toks)
