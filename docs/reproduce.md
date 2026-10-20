# Reproducing the archived analysis

This is a post-competition verification workflow. The original competition notebooks are preserved in `notebooks/`. The runner in `scripts/reproduce.py` executes their selected calculation cells locally without Colab upload/download prompts. It is not a newly discovered end-to-end pipeline.

## Required files

The repository includes `data/raw/costs.xlsx`, the small `data/processed/` rent and cost tables, and the reference CSVs under `results/`. Three larger archived files must also be placed at these exact paths:

| Path | Approximate size | Purpose |
|---|---:|---|
| `data/processed/transactions_deduplicated_audit.csv` | 73 MB | Revenue-side deduplicated transaction audit |
| `data/processed/transaction_date_candidates.csv` | 31 MB | Alternative dates for ambiguous transactions |
| `results/operating_costs/flight_costs.csv` | 2.7 MB | Flight-level reference for the first comparison |

Check that the CSV filenames have no added suffix such as ` (1)`. The first two tables were generated in the teammates' upstream analyses and are archived inputs here. The runner does **not** derive them from `data/raw/transactions.xlsx` or derive the rent tables from `data/raw/gates.xlsx`.

## Run locally

From the repository root, with Python 3.12 available:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/reproduce.py
```

On Windows, activate with `.venv\\Scripts\\activate` instead. The script writes recomputed CSVs and a machine-readable report to `results/reproduced/`, which is intentionally ignored by Git. A successful run prints `PASS: 26 complete output tables match the competition archive.`

The validation compares each complete CSV to the archived reference with numeric tolerance of CAD 0.01, records package versions, and reports 28,801 inferred flights, CAD 431,362,040.24 in operating costs, 558,129 deduplicated transactions, and CAD 370,629,024.85 in net transaction revenue. These values were reproduced in the preparation environment (Python 3.12.14, pandas 2.2.3, NumPy 2.3.5, openpyxl 3.1.5). Dependency versions in `requirements.txt` are not pinned, so an independent environment may require troubleshooting.

## Scope and limits

This validates the operating-cost calculations from raw cost records and the downstream integration/scenario calculations from archived revenue and gate inputs. It does not verify the upstream transaction cleaning/date-assignment and gate-allocation workflows from raw workbooks. It does not turn the hypothetical 40/60/80% avoidable-cost scenarios into realized savings.
