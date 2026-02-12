from __future__ import annotations
import os, glob, json, argparse, pathlib
from collections import defaultdict

def load_jsonl(p):
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                yield json.loads(s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="dir under results/scored/json/")
    ap.add_argument("--langs", default="hi,bn,ta,te,ml,mr,gu,kn,or,ur,ne,pa")
    ap.add_argument("--out", required=True, help="output CSV path")
    args = ap.parse_args()

    model_dir = os.path.join("results", "scored", "json", args.model)
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    pathlib.Path(os.path.dirname(args.out) or ".").mkdir(parents=True, exist_ok=True)

    rows = ["lang,native,romanized,mixed,n_native,n_romanized,n_mixed"]
    for L in langs:
        # Pick up all per-lang scored files (E1/E2xfer, any suffix)
        pats = [
            os.path.join(model_dir, f"scored_attacked_benign_{L}.jsonl"),
            os.path.join(model_dir, f"scored_attacked_benign_{L}_*.jsonl"),
            os.path.join(model_dir, f"scored_attacked_benign_{L}.*.jsonl"),
        ]
        files = []
        for pat in pats:
            files += glob.glob(pat)
        files = sorted(set(files))
        if not files:
            # silently skip missing lang
            continue

        bins = defaultdict(lambda: {"hits": 0, "n": 0})
        for fp in files:
            for r in load_jsonl(fp):
                # primary view = exclude explicit inference errors if present
                if r.get("inference_error", False):
                    continue
                if r.get("subset") != "attacked_benign":
                    continue
                ortho = r.get("orthography") or "native"
                hit = bool(r.get("jailbreak_success", False))
                bins[ortho]["n"] += 1
                bins[ortho]["hits"] += 1 if hit else 0

        def rate(k):
            n = bins[k]["n"]
            return (bins[k]["hits"] / n) if n else 0.0

        out = [
            L,
            f"{rate('native'):.4f}", f"{rate('romanized'):.4f}", f"{rate('mixed'):.4f}",
            str(bins['native']['n']), str(bins['romanized']['n']), str(bins['mixed']['n'])
        ]
        rows.append(",".join(out))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    print(f"[ok] wrote {args.out}")

if __name__ == "__main__":
    main()
