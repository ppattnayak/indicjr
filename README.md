# IndicJR: Indic Jailbreak Robustness Benchmark

This repository accompanies the IndicJR paper:

> **IndicJR: A Judge-Free Benchmark of Jailbreak Robustness in South Asian Languages**  


IndicJR (IJR) is a judge-free benchmark for evaluating adversarial jailbreak robustness
of large language models across 12 Indic and South Asian languages, covering both
contract-bound (JSON) and unconstrained (FREE) response settings.

## Overview

IndicJR evaluates:
- Jailbreak robustness under adversarial pressure
- Cross-lingual transfer of jailbreak attacks
- Orthographic variation (native, romanized, mixed scripts)
- Contract-bound vs free-form safety behavior
- Judge-free, fully automatic scoring

The benchmark spans **45,216 prompts** across 12 languages and multiple experimental tracks.

## Repository Status

⚠️ **This repository is being prepped for the final public release.**

Due to ongoing internal review and data governance checks, we currently provide:
- Dataset structure documentation
- Evaluation protocol description
- Reproducibility instructions
- Citation metadata

We will release prompt templates, scoring scripts, and processed datasets very soon. Stay tuned!

## Languages Covered

Bengali, Gujarati, Hindi, Kannada, Malayalam, Marathi, Nepali, Odia, Punjabi,
Tamil, Telugu, Urdu.

## Tracks

- **JSON Track**: Contract-bound refusal schema
- **FREE Track**: Unconstrained natural-language responses

## License

The code and documentation will be released under an open-source license.
Dataset licensing details will be provided with the full release.

## Citation

If you use IndicJR, please cite:

