import argparse, time, json
from ijr.utils.io import load_jsonl, write_jsonl
from ijr.runners.adapter_vllm import VLLMAdapter
from ijr.runners.adapter_openai import OpenAIAdapter

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--track", default="json")
    p.add_argument("--models", required=True)  # comma list
    p.add_argument("--langs", required=True)
    args=p.parse_args()

    # inside scripts/run_inference.py, replace prompts loading with per-lang reads
    langs = set(args.langs.split(","))
    prompts = []
    for lang in langs:
        path = f"ijr/data/prompts/{lang}.{args.track}.jsonl"
        if os.path.exists(path):
            prompts.extend(load_jsonl(path))
        else:
            print(f"[warn] missing {path}, skipping")

    models=args.models.split(",")

    for m in models:
        if m=="llama3_8b":
            adapter=VLLMAdapter("meta-llama/Meta-Llama-3-8B-Instruct")
        else:
            adapter=OpenAIAdapter("gpt-4o-mini")
        out=[]
        for pr in prompts:
            t0=time.time()
            resp=adapter.generate([{"prompt":pr["final_prompt"]}])[0]
            out.append({"prompt_id":pr["id"], "response_text":resp["text"], "usage":resp.get("usage",{}), "latency_ms":resp.get("latency_ms",int((time.time()-t0)*1000))})
        write_jsonl(f"results/raw/{args.track}/{m}/outputs.jsonl", out)

if __name__ == "__main__":
    main()
