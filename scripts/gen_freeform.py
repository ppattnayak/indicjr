from __future__ import annotations
import argparse, os, json, pathlib

def load_jsonl(p):
    with open(p, encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def append_jsonl(p, rows):
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p,"a",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False)+"\n")

def split_core(final_prompt: str):
    parts=[p for p in final_prompt.split("\n\n") if p.strip()]
    return ("\n\n".join(parts[:-1]), parts[-1]) if len(parts)>=2 else (final_prompt, "")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--langs", required=True, help="comma list")
    ap.add_argument("--families", default="instruction,format,translate")
    ap.add_argument("--out_dir", default="ijr/data/prompts_free")
    ap.add_argument("--per_lang", type=int, default=200)   # take 200 attacked-benign per lang
    args=ap.parse_args()

    langs=[x.strip() for x in args.langs.split(",") if x.strip()]
    fams=set(x.strip() for x in args.families.split(",") if x.strip())
    for L in langs:
        src=f"ijr/data/prompts/{L}.jsonl"
        if not os.path.exists(src): 
            print(f"[warn] missing {src}"); continue
        rows=[]
        for r in load_jsonl(src):
            if r.get("family") in fams and r.get("mode") in ("same","cross"):
                _, base = split_core(r["final_prompt"])
                if base:
                    rows.append({
                        "id": r["id"].replace("-cross","-free") if r["mode"]=="cross" else r["id"]+"-free",
                        "lang": L,
                        "subset": "attacked_benign",
                        "family": r["family"],
                        "mode": r["mode"],
                        "prompt": base   # free-form uses only the task text
                    })
        # light downsample
        rows = rows[:args.per_lang]
        dst=f"{args.out_dir}/{L}.jsonl"
        append_jsonl(dst, rows)
        print(f"[ok] wrote {len(rows)} → {dst}")

if __name__=="__main__":
    main()
