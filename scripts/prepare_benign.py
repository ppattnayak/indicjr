# scripts/prepare_benign.py
"""
Builds a benign task pool from public corpora (no translation needed).
- Sources (auto-fallback): Wikipedia snapshot -> OSCAR -> synthetic tiny fallback
- Tasks: summarize, extract bullets, 1-label classify
- Script filtering: keep items that look like the target script for the language
- De-duplication: hash-based + simple near-dup cutoff
"""
from __future__ import annotations
import argparse, hashlib, random, re, unicodedata, os
from typing import List, Dict, Iterable
from datasets import load_dataset, Dataset
from ijr.utils.io import write_jsonl
from ijr.utils.seed import seed_all
from ijr.utils.langcodes import LMAP
from ijr.utils.prompts import get_task_templates

# ---------- Script ranges by language (coarse but effective) ----------
# Unicode blocks for Indic scripts + Gurmukhi, Gujarati, Oriya, etc.
SCRIPT_RANGES = {
    "hi": [(0x0900, 0x097F)],      # Devanagari
    "ne": [(0x0900, 0x097F)],      # Devanagari
    "mr": [(0x0900, 0x097F)],      # Devanagari
    "bn": [(0x0980, 0x09FF)],      # Bengali/Assamese
    "as": [(0x0980, 0x09FF)],      # Bengali/Assamese
    "pa": [(0x0A00, 0x0A7F)],      # Gurmukhi
    "gu": [(0x0A80, 0x0AFF)],      # Gujarati
    "or": [(0x0B00, 0x0B7F)],      # Oriya (Odia)
    "ta": [(0x0B80, 0x0BFF)],      # Tamil
    "te": [(0x0C00, 0x0C7F)],      # Telugu
    "kn": [(0x0C80, 0x0CFF)],      # Kannada
    "ml": [(0x0D00, 0x0D7F)],      # Malayalam
}

def looks_like_lang(text: str, lang: str, min_ratio: float = 0.3) -> bool:
    rngs = SCRIPT_RANGES.get(lang)
    if not rngs:
        return True
    total = 0
    hits = 0
    for ch in text:
        if ch.isspace() or unicodedata.category(ch).startswith("P"):  # space/punct
            continue
        total += 1
        cp = ord(ch)
        if any(lo <= cp <= hi for (lo, hi) in rngs):
            hits += 1
    return total > 0 and (hits / total) >= min_ratio

def normalize_text(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def dedup(items: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for t in items:
        h = sha(t)
        if h in seen:
            continue
        seen.add(h)
        out.append(t)
    return out

def sample_corpus(lang: str, need: int) -> List[str]:
    """Try Wikipedia snapshot -> OSCAR -> tiny synthetic fallback."""
    iso = LMAP.get(lang, lang)
    pool: List[str] = []

    # 1) Wikipedia snapshot (Wikimedia)
    try:
        ds = load_dataset("wikimedia/wikipedia", f"20231101.{iso}", split="train")
        # take paragraphs that look like the language and moderate length
        for ex in ds.shuffle(seed=42).select(range(min(len(ds), need*10))):
            txt = ex.get("text") or ""
            txt = normalize_text(txt)
            if 400 <= len(txt) <= 1200 and looks_like_lang(txt, lang):
                pool.append(txt)
                if len(pool) >= need:
                    return pool
    except Exception:
        pass

    # 2) OSCAR (monolingual common crawl)
    try:
        # Note: OSCAR uses language codes like 'hi', 'bn', etc. Some may be missing.
        ds2 = load_dataset("oscar-corpus/OSCAR-2301", iso, split="train", streaming=True)
        for i, ex in enumerate(ds2):
            if len(pool) >= need:
                break
            txt = ex.get("text") or ""
            txt = normalize_text(txt)
            if 400 <= len(txt) <= 1200 and looks_like_lang(txt, lang):
                pool.append(txt)
                if len(pool) >= need:
                    break
    except Exception:
        pass

    # 3) Tiny synthetic fallback if nothing else worked (rare)
    if not pool:
        s = {
            "hi": "यह एक नमूना पाठ है जो विकिपीडिया अनुच्छेद जैसा दिखता है। इसमें कुछ पंक्तियाँ हैं ताकि सारांश कार्य यथार्थवादी लगे।",
            "bn": "এটি একটি নমুনা অনুচ্ছেদ, বাস্তব উইকিপিডিয়া টেক্সটের মতো। এতে কয়েকটি বাক্য আছে যাতে সারাংশ কাজটি বাস্তবসম্মত হয়।",
            "ta": "இது ஒரு மாதிரி பதிவாகும்; விக்கிப்பீடியா உரையைப் போன்றது. சுருக்கம் செய்ய சில வாக்கியங்கள் உள்ளன.",
            "te": "ఇది ఒక నమూనా పేరా; వికీపీడియా వచనం వంటి భావన ఇవ్వబడింది. సారాంశం కోసం కొన్ని వాక్యాలు ఉన్నాయి.",
            "ml": "ഇത് ഒരു സാമ്പിള്‍ പാരഗ്രാഫാണ്; വിക്കിപീഡിയയിലെ ലേഖനത്തെപ്പോലെ. സംഗ്രഹത്തിനായി ചില വാക്യങ്ങള്‍ ഉണ്ട്.",
            "kn": "ಇದು ಒಂದು ಮಾದರಿ ಪ್ಯಾರಾಗ್ರಾಫ್; ವಿಕಿಪೀಡಿಯ ಲೇಖನದಂತಿದೆ. ಸಾರಾಂಶಕ್ಕಾಗಿ ಕೆಲವು ವಾಕ್ಯಗಳಿವೆ.",
            "mr": "हा एक नमुना परिच्छेद आहे; विकिपीडिया मजकुरासारखा. सारांशासाठी काही वाक्ये दिली आहेत.",
            "or": "ଏହା ଗୋଟିଏ ନମୁନା ପରିଛେଦ; ଉଇକିପିଡିଆର ଟେକ୍ଷ୍ଟ ପରି। ସାରାଂଶ ପାଇଁ କିଛି ବାକ୍ୟ ଅଛି।",
            "pa": "ਇਹ ਇਕ ਨਮੂਨਾ ਪੈਰਾ ਹੈ; ਵਿਕੀਪੀਡੀਆ ਲਿਖਤ ਵਰਗਾ। ਸਾਰ ਲਈ ਕੁਝ ਵਾਕ ਹਨ।",
            "gu": "આ નમૂનાઓનો પરિછેદ છે; વિકિપીડિયા લખાણ જેવો. સારાંશ માટે થોડા વાક્યો છે.",
            "as": "ইয়াত এটা নমুনা অনুচ্ছেদ আছে; ৱিকিপিডিয়াৰ লিখন যেন লাগিছে। সংক্ষিপ্তৰ বাবে কেইটামান বাক্য আছে।",
            "ne": "यो एक नमूना अनुच्छेद हो; विकिपीडियाको पाठ जस्तै। संक्षेपका लागि केही वाक्यहरू छन्।",
        }.get(lang, "Sample paragraph in target language.")
        pool = [s] * need

    # de-dup and cap
    pool = dedup(pool)
    if len(pool) > need:
        random.shuffle(pool)
        pool = pool[:need]
    return pool

def build_items(lang: str, texts: List[str]) -> List[Dict]:
    tmpl = get_task_templates(lang)
    items = []
    for t in texts:
        ttype = random.choice(["summ", "extract", "classify"])
        if ttype == "summ":
            prompt = tmpl["summ"].format(text=t)
        elif ttype == "extract":
            prompt = tmpl["extract"].format(text=t)
        else:
            prompt = tmpl["classify"].format(text=t)
        items.append({
            "lang": lang,
            "type": "benign",
            "ttype": ttype,
            "text": t,
            "prompt": prompt
        })
    return items

# ... keep the rest of prepare_benign.py unchanged ...

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", required=True, help="comma list, e.g., hi,bn")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--mode", choices=["create","append","skip-existing"], default="skip-existing",
                    help="create=overwrite per-lang file; append=add; skip-existing=leave if present")
    args = ap.parse_args()

    seed_all(42)
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    os.makedirs("ijr/data/processed/benign", exist_ok=True)

    manifest = []
    for lang in langs:
        outfp = f"ijr/data/processed/benign/{lang}.jsonl"
        if args.mode == "skip-existing" and os.path.exists(outfp):
            print(f"[skip] {outfp} exists")
            manifest.append({"lang": lang, "path": outfp})
            continue

        texts = sample_corpus(lang, args.n)
        rows = build_items(lang, texts)

        if args.mode == "append" and os.path.exists(outfp):
            # append
            with open(outfp, "a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        else:
            # create/overwrite
            write_jsonl(outfp, rows)
        print(f"[ok] wrote {outfp} ({len(rows)})")
        manifest.append({"lang": lang, "path": outfp})

    # record a manifest (handy for later scripts)
    write_jsonl("ijr/data/processed/benign_manifest.jsonl", manifest)

if __name__ == "__main__":
    main()
