# InvestmentIntelligence cost and quality benchmark v1

This is a **standalone overlay**. It does not modify the investment pipeline, and it does not claim a vendor comparison has already occurred. Python standard library only. Run from the project root.

## Install

`unzip -o InvestmentIntelligence-benchmark-v1.zip`

`python -m unittest discover -s tests -p 'test_benchmark.py' -v`

## Prepare the ten-question benchmark

`python -m benchmark.runner init --output reports/benchmark-v1`

Ten fixed research questions (five NVDA, five MSFT) are in `benchmark/questions.json`. Preserve the exact question wording and evaluation cutoff for each comparator. Two competitor columns are placeholders, not claims that access is available.

## Execute InvestmentIntelligence

`python -m benchmark.runner run --output reports/benchmark-v1 --model qwen3:8b --as-of 2026-11-04`

This invokes the installed project CLI for each issuer. It measures wall time and child-process CPU time and captures logs. It **does not** claim to measure electricity, GPU utilization, API tokens, or dollars. Fill in the missing cost fields only from actual metering or invoices. If SEC/network data differs across runs, document the difference. Run uses the existing environment, including any configured `SEC_USER_AGENT`, Redis, and Ollama.

## Evaluate competitors fairly

Use the same 10 questions, as-of cutoff, source access scope, and human evaluator. Save each complete answer as a file. Fill `quality-scores.csv` for each tool/question. Grade six dimensions from **0 (failed) to 4 (strong)**: evidence discovery, observations vs inference, contradictory evidence, numerical integrity, uncertainty calibration, and decision usefulness. A row is scored only when all six grades, reviewer, and answer file are supplied. Keep source references in the sheet. Prefer blinded review and a second evaluator.

Fill `cost-ledger.csv` with one row per investigation and tool. Include all dollar fields (electricity, API, paid data, hardware amortization, other); **enter 0 only when verified to be zero**. Subscription tools should be assessed under explicit utilization assumptions (e.g. 10, 100, 1000 investigations/month) and show fixed and variable cost separately. Costs without complete fields are omitted, not imputed. Do not treat hardware sunk cost as free if comparing hosted services. This ledger measures **user-borne economics**, not the provider's unknown marginal cost.

`python -m benchmark.runner report --output reports/benchmark-v1`

Report remains `partial` until 30 answers are graded and 30 comparable cost rows are complete. Report generation does not imply comparable results. `run-metrics.json` and `benchmark-report.json` are suitable for upload and review.

## Scope limitations

The existing project may produce company-level reports rather than independent answers to each question. Human reviewers must assess whether the reports answer each question; do not treat the existence of a report as an answer. A missing or incomplete answer scores low, not as a successful investigation. Subscription prices must be verified with vendor quotes and licensing scope; no fabricated competitor outputs or prices are included.
