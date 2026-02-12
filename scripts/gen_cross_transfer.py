# scripts/gen_cross_transfer.py
from __future__ import annotations
import argparse, os, json, hashlib, pathlib, random
from typing import Dict, List, Tuple

PROMPTS_DIR = "ijr/data/prompts"

def load_jsonl(p: str):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def write_jsonl(p: str, rows: List[dict]):
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def append_jsonl_dedup(p: str, rows: List[dict]):
    """Append only rows whose id is not already present."""
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    if os.path.exists(p):
        for r in load_jsonl(p):
            rid = r.get("id")
            if rid:
                existing_ids.add(rid)
    new_rows = [r for r in rows if r.get("id") not in existing_ids]
    if not new_rows:
        return 0, len(rows)
    with open(p, "a", encoding="utf-8") as f:
        for r in new_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(new_rows), len(rows) - len(new_rows)

def hid(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]

def split_core(final_prompt: str) -> Tuple[str, str]:
    """
    Prompts are "<wrapper>\\n\\n<base benign block>".
    Return (wrapper, base). If unsure, treat all as wrapper.
    """
    parts = [p for p in final_prompt.split("\n\n") if p.strip()]
    if len(parts) >= 2:
        return "\n\n".join(parts[:-1]), parts[-1]
    return final_prompt, ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs",    required=True, help="comma list of target bases (L2), e.g., hi,bn,ta,te,ml,...")
    ap.add_argument("--sources",  required=True, help="comma list of wrapper sources (L1), e.g., hi,bn,ta,...")
    ap.add_argument("--families", default="instruction,format", help="families to transfer (same wrappers); e.g., instruction,format,translate")
    ap.add_argument("--per_pair", type=int, default=30, help="how many base items per (L1,L2) per family")
    ap.add_argument("--append", action="store_true",
                    help="Append into main {lang}.jsonl with de-dup (otherwise write/overwrite sidecar {lang}.xfer.jsonl)")
    ap.add_argument("--suffix", default="xfer",
                    help="Sidecar suffix when not using --append (default: xfer -> writes {lang}.xfer.jsonl)")
    args = ap.parse_args()

    targets = [x.strip() for x in args.langs.split(",") if x.strip()]
    sources = [x.strip() for x in args.sources.split(",") if x.strip()]
    fams    = [x.strip() for x in args.families.split(",") if x.strip()]

    # Cache native 'same' wrappers & bases
    wrappers: Dict[Tuple[str,str], List[str]] = {(L,f): [] for L in sources for f in fams}
    bases:    Dict[Tuple[str,str], List[str]] = {(L,f): [] for L in targets for f in fams}

    # Load once; gather wrapper (prefix) and base (last block)
    for L in sorted(set(sources + targets)):
        src = os.path.join(PROMPTS_DIR, f"{L}.jsonl")
        if not os.path.exists(src):
            continue
        for r in load_jsonl(src):
            if r.get("mode") != "same": 
                continue
            fam = r.get("family")
            if fam not in fams:
                continue
            wrap, base = split_core(r.get("final_prompt", ""))
            if L in sources:
                wrappers[(L, fam)].append(wrap)
            if L in targets and base:
                bases[(L, fam)].append(base)

    # Dedup while preserving order
    def _dedup(seq: List[str]) -> List[str]:
        seen = set(); out = []
        for s in seq:
            if s in seen: 
                continue
            seen.add(s); out.append(s)
        return out
    for k in list(wrappers.keys()):
        wrappers[k] = _dedup(wrappers[k])
    for k in list(bases.keys()):
        bases[k] = _dedup(bases[k])

    rng = random.Random(13)  # deterministic

    # Build cross-transfer rows
    out_by_L2: Dict[str, List[dict]] = {L2: [] for L2 in targets}
    for L1 in sources:
        for L2 in targets:
            if L1 == L2:
                continue
            for f in fams:
                W = wrappers.get((L1, f), [])
                B = bases.get((L2, f), [])
                if not W or not B:
                    continue
                k = min(args.per_pair, len(B))
                pick = rng.sample(B, k)
                for b in pick:
                    w = rng.choice(W)
                    final = f"{w}\n\n{b}"
                    pid = f"{L2}-{f}-cross-xfer-{L1}-{hid(final)}"
                    out_by_L2[L2].append({
                        "id": pid,
                        "lang": L2,
                        "family": f,
                        "mode": "cross",
                        "severity": "medium",
                        "final_prompt": final,
                        "metadata": {"xfer_source": L1}
                    })

    # Write
    total_new = total_skip = 0
    for L2, rows in out_by_L2.items():
        if not rows:
            continue
        if args.append:
            dst = os.path.join(PROMPTS_DIR, f"{L2}.jsonl")
            n_added, n_skipped = append_jsonl_dedup(dst, rows)
            total_new  += n_added
            total_skip += n_skipped
            print(f"[ok] appended {n_added} (skipped dup {n_skipped}) to {dst}")
        else:
            # write/overwrite sidecar to keep it clean/reproducible
            dst = os.path.join(PROMPTS_DIR, f"{L2}.{args.suffix}.jsonl")
            # de-dup within the batch by id for safety
            seen = set(); clean = []
            for r in rows:
                rid = r.get("id")
                if rid in seen: 
                    continue
                seen.add(rid); clean.append(r)
            write_jsonl(dst, clean)
            total_new += len(clean)
            print(f"[ok] wrote {len(clean)} to {dst}")

    print(f"[done] total new rows: {total_new}; skipped duplicates (append mode): {total_skip}")

if __name__ == "__main__":
    main()
