from transformers import AutoTokenizer

def frag_ratio(tokenizer_name, texts):
    tok=AutoTokenizer.from_pretrained(tokenizer_name, use_fast=True)
    ratios=[]
    for t in texts:
        ids=tok(t, add_special_tokens=False).input_ids
        ratios.append(len(ids)/max(1,len(t.split())))
    return sum(ratios)/len(ratios) if ratios else 0.0
