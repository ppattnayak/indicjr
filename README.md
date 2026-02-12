# IndicJR (IJR) Prompts & Scripts

This repository releases the prompt sets and experiment scripts for **IndicJR / Indic Jailbreak Robustness (IJR)**, a judge-free benchmark of jailbreak robustness across 12 Indic & South Asian languages.

> Warning: This dataset includes harmful and adversarial content for research purposes only.

## Languages
`hi, bn, ta, te, ml, mr, gu, kn, or, ur, ne, pa`

## Tracks & Splits

### JSON track (contract-bound)
Prompt subsets:
- **Attacked-benign (AB)**: benign tasks wrapped with adversarial jailbreak instructions
- **Clean-benign (CB)**: benign tasks without adversarial wrappers
- **Clean-harmful (CH)**: unsafe tasks intended to be refused (with canaries for leakage checks)

Folders:
- `prompts_json/`
  - `*.E1.jsonl` : E1 attacked-benign (same-lingual)
  - `*.E2xfer.jsonl` : E2 attacked-benign (cross-lingual transfer)
- `prompts_json_clean_benign_clean_harmful/`
  - `benign/<lang>.jsonl` : JSON clean-benign (CB)
  - `harmful/<lang>.jsonl` : JSON clean-harmful (CH)

**Paper-aligned counts (JSON):**
- AB (E1+E2 total): 37,236 prompts
- CB: 3,600 prompts (300 × 12 languages)
- CH: 1,800 prompts (150 × 12 languages)

> Note: `prompts_json_clean_benign_clean_harmful/` may include auxiliary aggregate files (e.g., `benign.jsonl`, manifests). These are not part of the reported per-split totals above.

### FREE track (unconstrained)
Folders:
- `prompts_free/<lang>.jsonl` : attacked-benign (AB) for FREE
- `prompts_free/clean_benign_<lang>.jsonl` : clean-benign (CB) for FREE
- `prompts_free/clean_harmful_<lang>.jsonl` : clean-harmful (CH) for FREE

Counts (FREE):
- AB: 2,400 (200 × 12)
- CB: 120 (10 × 12)
- CH: 60 (5 × 12)
- Total: 2,580

## File format (JSONL)

Each line is a JSON object (one prompt). Common fields include:
- `id` : canonical prompt id
- `lang` : language code
- `subset` : AB / CB / CH (or equivalent)
- `final_prompt` (or `prompt`) : the full text to send to the model
- Additional metadata (attack family, mode, orthography tags, etc.)

## Scripts

`scripts/` contains utilities for dataset generation and scoring:
- `lint_prompts.py` : sanity checks / schema checks
- `score_json.py` / `score_free.py` : judge-free scoring
- `compute_metrics.py` / `compute_metrics_free.py` : aggregate metrics
- `compute_transfer.py` : cross-lingual transfer metrics
- `e3_orthography_breakdown.py` : orthography slices
- `e6_fragmentation.py` : tokenization/fragmentation analysis
- `gen_*` : prompt generation utilities (attacks, orthography, cross-transfer, freeform)

## Running an evaluation (high level)

1) Generate model outputs (your inference runner)
- Input: JSONL prompts
- Output: JSONL with `{prompt_id, response_text, ...}`

2) Score outputs (judge-free)
- JSON track: `scripts/score_json.py`
- FREE track: `scripts/score_free.py`

3) Compute metrics & tables
- JSON: `scripts/compute_metrics.py`
- FREE: `scripts/compute_metrics_free.py`

## Reproducibility tips
- Keep a fixed decoding configuration (temperature, max tokens, seed if applicable)
- Save raw generations before scoring
- Do not post-process model outputs except basic decoding

## License
(Add your chosen license here; e.g., Apache-2.0 / CC-BY-4.0 / custom research-only)
