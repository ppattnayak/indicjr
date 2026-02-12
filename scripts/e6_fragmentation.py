# scripts/e6_fragmentation.py
from __future__ import annotations
import os, re, json, glob, argparse, hashlib, unicodedata, math
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import pandas as pd

# --- Where things live ---
PROMPTS_DIR = "ijr/data/prompts"
SCORED_DIR  = "results/scored/json"     # scored_attacked_benign_<lang>.jsonl
OUTDIR      = "results/summary"

SUBSET = "attacked_benign"              # we analyze attacked-benign only

# --- Try SciPy for Spearman/Kendall; fall back to pandas corr if missing ---
try:
    from scipy.stats import spearmanr
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

# ---------- Utilities ----------
def load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                yield json.loads(s)

def split_core(final_prompt: str) -> Tuple[str, str]:
    """Return (wrapper, base). We formatted prompts as: <wrapper>\n\n<base>."""
    parts = [p for p in final_prompt.split("\n\n") if p.strip()]
    if len(parts) >= 2:
        return "\n\n".join(parts[:-1]), parts[-1]
    return final_prompt, ""

def ortho_of_id(pid: str) -> str:
    """Infer orthography bucket from prompt id."""
    # Examples we used:
    #   ...-ortho{rom|mix}-<hash>
    # or checks: "-ortho" & "rom"/"mix"
    s = pid
    if ("-ortho" in s and "rom" in s) or "-orthorom-" in s:
        return "romanized"
    if ("-ortho" in s and "mix" in s) or "-orthomix-" in s:
        return "mixed"
    return "native"

def script_class(ch: str) -> str:
    """Very light script classifier for fragmentation proxies."""
    cp = ord(ch)
    # Latin
    if 0x0041 <= cp <= 0x024F or 0x1E00 <= cp <= 0x1EFF:
        return "Latin"
    # Devanagari (hi/ne)
    if 0x0900 <= cp <= 0x097F:
        return "Deva"
    # Bengali (bn)
    if 0x0980 <= cp <= 0x09FF:
        return "Beng"
    # Gurmukhi (pa)
    if 0x0A00 <= cp <= 0x0A7F:
        return "Gurm"
    # Gujarati (gu)
    if 0x0A80 <= cp <= 0x0AFF:
        return "Gujr"
    # Oriya (Odia) (or)
    if 0x0B00 <= cp <= 0x0B7F:
        return "Orya"
    # Tamil (ta)
    if 0x0B80 <= cp <= 0x0BFF:
        return "Taml"
    # Telugu (te)
    if 0x0C00 <= cp <= 0x0C7F:
        return "Telu"
    # Kannada (kn)
    if 0x0C80 <= cp <= 0x0CFF:
        return "Knda"
    # Malayalam (ml)
    if 0x0D00 <= cp <= 0x0D7F:
        return "Mlym"
    # Arabic (ur)
    if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF:
        return "Arab"
    # digits / ASCII punctuation
    if ch.isdigit(): return "Digit"
    if ch.isspace(): return "Space"
    cat = unicodedata.category(ch)
    if cat.startswith("P"): return "Punct"
    return "Other"

def frag_proxies(text: str) -> Dict[str, float]:
    """Compute cheap proxies for subword fragmentation on wrapper text."""
    if not text:
        return dict(tokens_per_char=float("nan"), ascii_ratio=float("nan"),
                    latin_ratio=float("nan"), script_switches_per100=float("nan"),
                    mean_run_len=float("nan"), word_len=float("nan"),
                    bytes_per_char=float("nan"))

    # chars/bytes
    n_chars = len(text)
    n_bytes = len(text.encode("utf-8"))
    bytes_per_char = n_bytes / max(1, n_chars)

    # "tokens_per_char": approximate with whitespace tokens
    words = re.findall(r"\S+", text, flags=re.UNICODE)
    n_words = len(words)
    tokens_per_char = n_words / max(1, n_chars)
    word_len = (sum(len(w) for w in words) / max(1, n_words)) if n_words else float("nan")

    # ascii / latin ratios
    ascii_ratio = sum(1 for ch in text if ord(ch) < 128) / max(1, n_chars)
    latin_ratio = sum(1 for ch in text if script_class(ch) == "Latin") / max(1, n_chars)

    # script run stats
    classes = [script_class(ch) for ch in text if not ch.isspace()]
    switches = sum(1 for i in range(1, len(classes)) if classes[i] != classes[i-1])
    script_switches_per100 = 100.0 * switches / max(1, len(classes))

    # mean run length
    if not classes:
        mean_run_len = float("nan")
    else:
        runs = 1
        for i in range(1, len(classes)):
            if classes[i] != classes[i-1]:
                runs += 1
        mean_run_len = len(classes) / runs if runs else float("nan")

    return dict(tokens_per_char=tokens_per_char, ascii_ratio=ascii_ratio,
                latin_ratio=latin_ratio, script_switches_per100=script_switches_per100,
                mean_run_len=mean_run_len, word_len=word_len, bytes_per_char=bytes_per_char)

def safe_spearman(x, y) -> Tuple[float, float]:
    """Return (rho, p). Falls back to rank corr via pandas if SciPy missing."""
    s = pd.Series(x).astype(float)
    t = pd.Series(y).astype(float)
    mask = s.notna() & t.notna()
    s, t = s[mask], t[mask]
    if len(s) < 3:
        return float("nan"), float("nan")
    if HAVE_SCIPY:
        rho, p = spearmanr(s.values, t.values)
        return float(rho), float(p)
    # fallback: Spearman = Pearson on ranks
    sr = s.rank()
    tr = t.rank()
    rho = sr.corr(tr, method="pearson")
    return float(rho), float("nan")

# ---------- Core pipeline ----------
def build_id2prompt(lang: str) -> Dict[str, str]:
    """
    Map prompt_id -> final_prompt.
    Command-A canonical: <lang>.E1.jsonl, <lang>.E2xfer.jsonl
    Keep Command-R fallbacks too: <lang>.jsonl, <lang>.xfer.jsonl, <lang>.ortho.jsonl
    """
    id2p = {}
    candidates = [
        f"{lang}.E1.jsonl",
        f"{lang}.E2xfer.jsonl",
        f"{lang}.jsonl",
        f"{lang}.xfer.jsonl",
        f"{lang}.ortho.jsonl",
    ]
    for side in candidates:
        p = os.path.join(PROMPTS_DIR, side)
        if not os.path.exists(p):
            continue
        for r in load_jsonl(p):
            pid = r.get("id")
            fp  = r.get("final_prompt") or r.get("prompt") or ""
            if pid and fp:
                id2p[pid] = fp
    return id2p


def collect_jsr_and_frag(model_dir: str, lang: str, families: Optional[List[str]]) -> pd.DataFrame:
    """
    For a given model/lang:
      - read scored_attacked_benign_<lang>.jsonl
      - compute JSR per (family, ortho)
      - compute fragmentation proxies on WRAPPER for each id, then mean per (family, ortho)
      - return tidy rows for (lang, family, ortho)
    """
        # Accept multiple per-lang files (e.g., _E1.jsonl, _E2xfer.jsonl, dot/underscore variants)
    patterns = [
        os.path.join(model_dir, f"scored_{SUBSET}_{lang}.jsonl"),
        os.path.join(model_dir, f"scored_{SUBSET}_{lang}_*.jsonl"),
        os.path.join(model_dir, f"scored_{SUBSET}_{lang}.*.jsonl"),
    ]
    scored_paths = []
    for pat in patterns:
        scored_paths += glob.glob(pat)
    scored_paths = sorted(set(scored_paths))
    if not scored_paths:
        return pd.DataFrame()

    id2prompt = build_id2prompt(lang)

    rows = []
    for spath in scored_paths:
        for r in load_jsonl(spath):
            fam = r.get("family","")
            if families and fam not in families:
                continue
            if r.get("mode") != "same":
                continue
            pid = r.get("prompt_id","")
            ortho = ortho_of_id(pid)
            jsr = bool(r.get("jailbreak_success", False))
            fp = id2prompt.get(pid, "")
            wrap, _ = split_core(fp)
            proxies = frag_proxies(wrap)
            rows.append({
                "lang": lang,
                "family": fam,
                "ortho": ortho,
                "jsr": jsr,
                **proxies
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # aggregate to mean JSR / mean proxies per (lang, family, ortho)
    agg = df.groupby(["lang","family","ortho"], as_index=False).agg({
        "jsr":"mean",
        "tokens_per_char":"mean",
        "ascii_ratio":"mean",
        "latin_ratio":"mean",
        "script_switches_per100":"mean",
        "mean_run_len":"mean",
        "word_len":"mean",
        "bytes_per_char":"mean",
    }).rename(columns={"jsr":"JSR"})
    return agg

def add_deltas(agg: pd.DataFrame) -> pd.DataFrame:
    """
    From rows at (lang,family,ortho) with ortho in {native,romanized,mixed},
    pivot and compute Δrom-nat, Δmix-nat for both JSR and frag proxies.
    """
    piv = agg.pivot_table(index=["lang","family"], columns="ortho", values=[
        "JSR","tokens_per_char","ascii_ratio","latin_ratio",
        "script_switches_per100","mean_run_len","word_len","bytes_per_char"
    ])
    # helper to compute deltas safely
    def dcol(a,b): 
        return piv[a].get("romanized", pd.Series()) - piv[a].get("native", pd.Series()) if b=="rom" else \
               piv[a].get("mixed",      pd.Series()) - piv[a].get("native", pd.Series())

    out = pd.DataFrame(index=piv.index)
    # JSR deltas
    out["ΔJSR_rom_nat"] = piv["JSR"].get("romanized", pd.Series()) - piv["JSR"].get("native", pd.Series())
    out["ΔJSR_mix_nat"] = piv["JSR"].get("mixed",      pd.Series()) - piv["JSR"].get("native", pd.Series())

    # fragmentation deltas (romanized/mixed minus native)
    for metric in ["tokens_per_char","ascii_ratio","latin_ratio","script_switches_per100","mean_run_len","word_len","bytes_per_char"]:
        out[f"Δ{metric}_rom_nat"] = dcol(metric, "rom")
        out[f"Δ{metric}_mix_nat"] = dcol(metric, "mix")

    out = out.reset_index()
    return out

def correlate(deltas: pd.DataFrame, family: Optional[str]=None) -> pd.DataFrame:
    """
    Spearman correlations between ΔJSR and Δfrag proxies across (lang, family) rows.
    If family is None => pool all families; else filter.
    """
    df = deltas.copy()
    if family:
        df = df[df["family"]==family].copy()
    if df.empty:
        return pd.DataFrame()

    rows=[]
    for target in ["rom_nat","mix_nat"]:
        y = df[f"ΔJSR_{target}"]
        for m in ["tokens_per_char","ascii_ratio","latin_ratio","script_switches_per100","mean_run_len","word_len","bytes_per_char"]:
            x = df[f"Δ{m}_{target}"]
            rho, p = safe_spearman(x, y)
            rows.append({
                "family": family if family else "ALL",
                "target": target,        # which delta
                "metric": m,
                "rho": rho,
                "pvalue": p,
                "n": int(pd.concat([x,y], axis=1).dropna().shape[0])
            })
    return pd.DataFrame(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=None,
                    help="comma list of model dir names under results/scored/json/. Default: all present.")
    ap.add_argument("--langs", default=None,
                    help="comma list of langs to include (default: infer from scored files).")
    ap.add_argument("--families", default="instruction,format,roleplay,translate",
                    help="families to include for analysis (comma list).")
    ap.add_argument("--out_prefix", default="e6_fragmentation_cmdR",
                    help="prefix for CSVs written to results/summary/")
    args = ap.parse_args()

    families = [x.strip() for x in args.families.split(",") if x.strip()]
    models = []
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        # autodetect scored models
        models = [os.path.basename(p) for p in glob.glob(os.path.join(SCORED_DIR,"*")) if os.path.isdir(p)]
    if not models:
        raise SystemExit("[err] No scored models found under results/scored/json")

    os.makedirs(OUTDIR, exist_ok=True)

    # we’ll do this per model and then concatenate with a "model" col
    all_summaries = []
    all_deltas = []
    all_corrs   = []

    for model in models:
        model_dir = os.path.join(SCORED_DIR, model)
        # langs to include:
        if args.langs:
            langs = [x.strip() for x in args.langs.split(",") if x.strip()]
        else:
            # infer base lang from scored filenames: take the token before first '_' or '.'
            langs_set = set()
            for p in glob.glob(os.path.join(model_dir, f"scored_{SUBSET}_*.jsonl")):
                suf = os.path.basename(p).split(f"scored_{SUBSET}_", 1)[1].replace(".jsonl","")
                # e.g., "hi_E1" -> "hi", "bn.E2xfer" -> "bn"
                base = re.split(r"[_.]", suf, 1)[0]
                if base and ("," not in base) and ("-" not in base):
                    langs_set.add(base)
            langs = sorted(langs_set)


        # gather per (lang,family,ortho)
        agg_rows = []
        for L in langs:
            df = collect_jsr_and_frag(model_dir, L, families)
            if not df.empty:
                df["model"] = model
                agg_rows.append(df)
        if not agg_rows:
            print(f"[warn] no rows for model={model}")
            continue

        agg = pd.concat(agg_rows, ignore_index=True)
        all_summaries.append(agg)

        # compute deltas
        dels = add_deltas(agg)
        dels["model"] = model
        all_deltas.append(dels)

        # correlations pooled + per-family
        cor_all = correlate(dels, family=None)
        cor_all["model"] = model
        all_corrs.append(cor_all)
        for fam in sorted(agg["family"].unique()):
            cor_f = correlate(dels, family=fam)
            cor_f["model"] = model
            all_corrs.append(cor_f)

    if not all_summaries:
        raise SystemExit("[err] Nothing to write; check inputs.")

    df_summary = pd.concat(all_summaries, ignore_index=True)
    df_deltas  = pd.concat(all_deltas, ignore_index=True)
    df_corrs   = pd.concat(all_corrs, ignore_index=True)

    # write CSVs
    p1 = os.path.join(OUTDIR, f"{args.out_prefix}_summary_by_lang_family_ortho.csv")
    p2 = os.path.join(OUTDIR, f"{args.out_prefix}_deltas_by_lang_family.csv")
    p3 = os.path.join(OUTDIR, f"{args.out_prefix}_correlations.csv")

    df_summary.to_csv(p1, index=False)
    df_deltas.to_csv(p2, index=False)
    df_corrs.to_csv(p3, index=False)

    # quick console peek
    print(f"[ok] wrote {p1}  ({len(df_summary)} rows)")
    print(f"[ok] wrote {p2}  ({len(df_deltas)} rows)")
    print(f"[ok] wrote {p3}  ({len(df_corrs)} rows)")

if __name__ == "__main__":
    main()
