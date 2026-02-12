# scripts/compare_tracks_lang_rank.py
from __future__ import annotations
import argparse, os, json, glob, math
from collections import defaultdict
import pandas as pd

SUBSET = "attacked_benign"
FAMS   = ["instruction","translate","roleplay","format"]

def load_jsonl(p):
    with open(p, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                yield json.loads(s)
            except Exception as e:
                raise RuntimeError(f"Bad JSON at {p}:{ln}") from e

def exists(p): return os.path.exists(p)

def jsr_from_rows(rows):
    # mean of jailbreak_success True/False
    arr = [bool(r.get("jailbreak_success")) for r in rows]
    return (sum(arr)/len(arr)) if arr else float("nan")

def jsr_by_family(rows):
    bins = defaultdict(list)
    for r in rows:
        fam = r.get("family","")
        if fam: bins[fam].append(bool(r.get("jailbreak_success")))
    return {k:(sum(v)/len(v) if v else float("nan")) for k,v in bins.items()}

def read_scored(track_dir, model, lang, suffix=""):
    base = f"results/scored/{track_dir}/{model}"
    if track_dir == "json":
        fp = os.path.join(base, f"scored_{SUBSET}_{lang}.jsonl")
    else:
        # free
        fp = os.path.join(base, f"scored_{SUBSET}_{lang}{suffix}.jsonl")
    if not exists(fp):
        return None, None, fp
    rows = list(load_jsonl(fp))
    return rows, fp, None

def rank_series(values_dict, descending=True):
    """
    values_dict: {lang: value}
    Returns a DataFrame with columns: value, rank
    Ties get average rank (method='average').
    """
    s = pd.Series(values_dict, dtype=float, name="value")
    # ranks: highest value gets rank 1 if descending=True
    s_rank = s.rank(ascending=not descending, method="average")
    return pd.DataFrame({"value": s, "rank": s_rank})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="e.g., oci_cohere_cmdr")
    ap.add_argument("--langs", required=True,
                    help="comma list of ISO-2 codes in your run order")
    ap.add_argument("--free_suffix", default="_free",
                    help="suffix used in free files, default=_free")
    ap.add_argument("--out_prefix", required=True,
                    help="prefix for outputs, e.g., results/summary/cmdR_json_vs_free")
    args = ap.parse_args()

    langs = [x.strip() for x in args.langs.split(",") if x.strip()]

    # --- gather per-lang metrics for both tracks
    recs = []
    missing = []
    for L in langs:
        rows_json,  fp_json,  miss_json  = read_scored("json",  args.model, L, "")
        rows_free,  fp_free,  miss_free  = read_scored("free",  args.model, L, args.free_suffix)
        if rows_json is None or rows_free is None:
            missing.append((L, miss_json or "", miss_free or ""))
            continue

        jsr_all_json  = jsr_from_rows(rows_json)
        jsr_all_free  = jsr_from_rows(rows_free)
        fam_json      = jsr_by_family(rows_json)
        fam_free      = jsr_by_family(rows_free)

        rec = {"lang": L,
               "JSR_json": jsr_all_json, "JSR_free": jsr_all_free}
        for fam in FAMS:
            rec[f"JSR_json_{fam}"] = fam_json.get(fam, float("nan"))
            rec[f"JSR_free_{fam}"] = fam_free.get(fam, float("nan"))
            rec[f"Delta_{fam}"]    = rec[f"JSR_free_{fam}"] - rec[f"JSR_json_{fam}"]
        recs.append(rec)

    if missing:
        print("[warn] Missing scored files for languages:")
        for L, mj, mf in missing:
            print(f"  - {L}: json_missing={mj} free_missing={mf}")

    df = pd.DataFrame(recs).sort_values("lang")
    os.makedirs(os.path.dirname(args.out_prefix), exist_ok=True)
    df.to_csv(f"{args.out_prefix}_lang_jsr_by_family.csv", index=False)

    # --- language ranking per family: JSON vs FREE
    rank_rows = []
    corr_rows = []
    for fam in FAMS:
        vals_json = {r["lang"]: r[f"JSR_json_{fam}"] for _, r in df.iterrows() if not math.isnan(r[f"JSR_json_{fam}"])}
        vals_free = {r["lang"]: r[f"JSR_free_{fam}"] for _, r in df.iterrows() if not math.isnan(r[f"JSR_free_{fam}"])}

        common_langs = sorted(set(vals_json) & set(vals_free))
        if len(common_langs) < 2:
            continue

        rj = rank_series({L: vals_json[L] for L in common_langs})
        rf = rank_series({L: vals_free[L] for L in common_langs})
        rtab = (rj[["rank"]].rename(columns={"rank":"rank_json"})
                  .join(rf[["rank"]].rename(columns={"rank":"rank_free"}), how="inner"))
        rtab["Δrank_free_minus_json"] = rtab["rank_free"] - rtab["rank_json"]
        rtab["family"] = fam
        rtab["lang"]   = rtab.index
        rank_rows.append(rtab.reset_index(drop=True))

        # correlations of **values** (not ranks) are more interpretable here
        try:
            from scipy.stats import spearmanr, kendalltau
            import numpy as np
            vj = np.array([vals_json[L] for L in common_langs], dtype=float)
            vf = np.array([vals_free[L] for L in common_langs], dtype=float)
            sp = spearmanr(vj, vf, nan_policy="omit")
            kt = kendalltau(vj, vf, nan_policy="omit")
            corr_rows.append({"family":fam,
                              "N": len(common_langs),
                              "spearman_rho": float(sp.correlation) if sp.correlation is not None else float("nan"),
                              "spearman_p":   float(sp.pvalue)      if sp.pvalue      is not None else float("nan"),
                              "kendall_tau":  float(kt.correlation) if kt.correlation is not None else float("nan"),
                              "kendall_p":    float(kt.pvalue)      if kt.pvalue      is not None else float("nan")})
        except Exception:
            pass

    rank_tbl = pd.concat(rank_rows, ignore_index=True) if rank_rows else pd.DataFrame(columns=["family","lang","rank_json","rank_free","Δrank_free_minus_json"])
    corr_tbl = pd.DataFrame(corr_rows).sort_values("family") if corr_rows else pd.DataFrame(columns=["family","N","spearman_rho","spearman_p","kendall_tau","kendall_p"])

    # deltas wide (Free − JSON) per family
    delta_wide = df[["lang"] + [f"Delta_{f}" for f in FAMS]].set_index("lang")

    # write all artifacts
    rank_tbl.to_csv(f"{args.out_prefix}_lang_rank_table.csv", index=False)
    corr_tbl.to_csv(f"{args.out_prefix}_lang_rank_correlations.csv", index=False)
    delta_wide.to_csv(f"{args.out_prefix}_lang_deltas_wide.csv")

    print(f"[ok] wrote {args.out_prefix}_lang_jsr_by_family.csv")
    print(f"[ok] wrote {args.out_prefix}_lang_rank_table.csv  (rows={len(rank_tbl)})")
    print(f"[ok] wrote {args.out_prefix}_lang_rank_correlations.csv")
    print(f"[ok] wrote {args.out_prefix}_lang_deltas_wide.csv")

if __name__ == "__main__":
    main()
