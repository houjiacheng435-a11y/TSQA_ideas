---
license: cc-by-4.0
language:
- en
task_categories:
- question-answering
- time-series-forecasting
tags:
- time-series
- nilm
- energy
- uk-dale
- needle-in-a-haystack
- long-context
pretty_name: UK-DALE-Haystack
size_categories:
- 10K<n<100K
---

# UK-DALE-Haystack

A controlled additive-needle benchmark for **long-context time-series language
models** built on top of UK-DALE (Kelly & Knottenbelt, 2015), the canonical
UK domestic appliance-level + whole-house power demand dataset.

Each sample is a 6-second-sampled mains active-power trace with one or more
real per-appliance bouts inserted at known locations. A QA prompt asks the
model to detect, count, localize, order, or reason about those bouts across
five context lengths from 15 minutes to 24 hours.

## Quick stats

- **10 task families** (existence, localization, counting, ordering,
  antecedent, comparison, multi-hop, state_query, anomaly_detection,
  anomaly_localization).
- **5 context lengths**: 900 s, 3600 s, 7200 s, 32400 s, 86400 s
  (15 min, 1 h, 2 h, 9 h, 24 h).
- **Per (task, ctx, split)**: 1000 train / 150 val / 150 test (≈65 K samples).
- **3 houses kept** from UK-DALE (h1, h2, h5); 290 ISO-weeks split 80/10/10
  by (house, week) at seed=42.
- Bouts and backgrounds are real; insertion is sample-by-sample additive
  (no style transfer, no blending, no scaling).

## Layout

```
uk_dale_haystack/
├── manifest.json           dataset metadata (houses, appliances, regimes)
├── source_manifest.json    sha256 pin of the source UK-DALE HDF5
├── split_manifest.json     (house, ISO-week) → train/val/test
├── bout_index.parquet      one row per ON-event, split-pinned
├── bout_index_stats.json   per-appliance bout summary
├── tasks/{ctx}s/{task}/{split}/data.parquet   QA samples (metadata only)
├── signals/h{B}/m{M}.npy   float32 watts memmap per (house, meter)
├── signals/h{B}/m{M}.t.npy int64 unix-ns timestamps memmap (paired)
├── signals/conversion_manifest.json  HDF5→npy conversion provenance
└── diagnostics/            insertion-shortcut probe results (optional)
```

QA shards are **lightweight metadata only** — the mains trace for each
sample is reconstructed at load time from `background_house_id`,
`background_start_ns/end_ns`, and `needles_json`, by reading the npy
sidecars in `signals/`. Both `signals/` and `tasks/` are required for use.

## How to use

The accompanying codebase lives at the project repository (see
`src/datasets/uk_dale_haystack/`) and provides loaders, samplers, and
configs that consume this layout directly.

Download:

```bash
python scripts/data/download_from_hf.py --dataset uk-dale-haystack
```

This places everything under `data/uk_dale/uk_dale_haystack/`, ready for
the runtime loader (`src.datasets.uk_dale_haystack.qa_dataset.UKDaleHaystackQADataset`).
Training configs: `configs/paper/{flamingo,chattime,chatts,itformer}_uk_dale_haystack.yaml`.

## Reproducibility

Every sample is generated with `rng = default_rng(seed)` where
`seed = md5(master_seed | task | ctx_s | split | sample_idx)`. Two
generation runs with the same `master_seed` produce identical parquet
shards (verified by `tests/integration/test_uk_dale_reproducibility.py`).

To regenerate from the source HDF5:

```bash
.venv/bin/python -m scripts.data.build_uk_dale_manifest
.venv/bin/python scripts/data/convert_uk_dale_to_npy.py
.venv/bin/python scripts/data/build_uk_dale_bout_index.py --overwrite
.venv/bin/python scripts/data/build_uk_dale_haystack.py --overwrite
```

The full design document, validation results (insertion-shortcut probe,
classifier transfer, sim-to-real gap analysis), and limitations are in
`src/datasets/uk_dale_haystack/DATASET_CARD.md` in the codebase.

## Source & license

- **Source dataset:** UK-DALE — Kelly J., Knottenbelt W., "The UK-DALE
  dataset, domestic appliance-level electricity demand and whole-house
  demand from five UK homes," *Sci. Data* 2:150007, 2015.
- **License:** CC-BY-4.0 (inherited from UK-DALE; this derivative
  preserves the attribution requirement).
- **Source pin:** sha256
  `5cb9c07ec0da0ac4cc9e1a6ee6a7ba76561f4fe4367e6de78addaa2a63432092`
  on the NILMTK HDF5 export (5.896 GB).

## Citation

If you use UK-DALE-Haystack, please cite the original UK-DALE dataset:

```
@article{kelly2015ukdale,
  title   = {The UK-DALE dataset, domestic appliance-level electricity
             demand and whole-house demand from five UK homes},
  author  = {Kelly, Jack and Knottenbelt, William},
  journal = {Scientific Data},
  volume  = {2},
  pages   = {150007},
  year    = {2015}
}
```
