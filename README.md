# InvestmentIntelligence

**An evidence-driven financial research and analysis system built on OpenAgentFabric and SECAgents.**

InvestmentIntelligence combines deterministic financial analysis, SEC filing retrieval, structured investigations, and LLM-assisted interpretation into an integrated research workflow.

Rather than asking a language model to evaluate a company's financial statements directly, the system separates financial observations, analytical calculations, supporting evidence, and qualitative interpretation.

## Architecture

InvestmentIntelligence is the application layer of a three-project architecture:

| Component | Responsibility |
|---|---|
| [OpenAgentFabric](https://github.com/costab06/OpenAgentFabric) | Agent orchestration, workflow execution, recovery, and reliability infrastructure |
| [SECAgents](https://github.com/costab06/SECAgents) | SEC filing retrieval, parsing, and financial data extraction |
| InvestmentIntelligence | Financial analysis, evidence evaluation, research investigations, and reporting |

The separation allows each component to evolve independently while providing a coordinated research workflow.

## Capabilities

### Deterministic financial analysis

Calculates financial metrics from structured observations, including growth, profitability, cash generation, and balance-sheet measures.

Financial observations retain source information and are subject to validation before use.

### Evidence-based investigations

Supports research into capital investment, earnings quality, financial history, industry context, and related financial questions.

Evidence retrieval and validation are distinct from the interpretation of that evidence.

### Controlled LLM interpretation

Language models assist with qualitative analysis and narrative synthesis.

Generated commentary is subject to validation and review controls. Rejected commentary does not eliminate independently verified financial observations.

### Research reporting

Produces structured analysis artifacts and human-readable reports, supporting inspection of findings and their underlying evidence.

### Benchmarking

Includes a reproducible benchmarking framework for evaluating research quality, completeness, and execution characteristics.

See [README-BENCHMARK.md](README-BENCHMARK.md).

## Requirements

- Python 3.12 or newer
- OpenAgentFabric v0.2.x
- SECAgents v0.2.x
- Additional dependencies required by the integrated runtime

## Installation

Install the two underlying projects from their public GitHub repositories before installing InvestmentIntelligence.

```bash
python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip

python -m pip install \
  "git+https://github.com/costab06/OpenAgentFabric.git@v0.2.1"

python -m pip install \
  "git+https://github.com/costab06/SECAgents.git@v0.2.0"

python -m pip install -e .
```

Verify the installation:

```bash
python -m pip check
python -m pytest tests/ -q
```

The v1.0.0 release was validated against 178 automated tests.

## Running InvestmentIntelligence

InvestmentIntelligence provides a single-command research pipeline.

### Basic financial analysis

Run the financial analysis pipeline without the optional broader investigation stages:

```bash
python -m investment_intelligence \
  --ticker MSFT \
  --financials-only \
  --output reports/msft-financials
```

### Full research investigation

Run the integrated research pipeline:

```bash
python -m investment_intelligence \
  --ticker MSFT \
  --as-of 2026-11-04 \
  --model qwen3:8b \
  --output reports/msft-investigation
```

The full investigation may require configured services, including an LLM endpoint, Redis, and access to the relevant SEC data sources.

The `--model` option selects the language model. `--base-url`, `--redis-url`, and `--sec-stream` allow runtime service configuration.

### Industry research

Industry context can be configured through reviewed research inputs:

- `--industry-mapping`: JSON mapping of companies to BEA industry series.
- `--industry-claims`: Structured industry-premise claims.
- `--industry-hypotheses`: Company and industry research hypotheses.
- `--no-auto-industry`: Disables automatic reviewed industry mapping.

These inputs support explicit, inspectable assumptions rather than silently treating generated industry hypotheses as established facts.

### Command-line reference

```bash
python -m investment_intelligence --help
```

### Separate SEC financial reporting interface

The package also provides a standalone reporting command:

```bash
investment-report --help
```

This interface produces SEC-based financial reports independently of the full research pipeline.

### Benchmarking

The repository includes a reproducible benchmark framework under `benchmark/`.

See [README-BENCHMARK.md](README-BENCHMARK.md) for benchmark execution and evaluation instructions.

## Research methodology

The system emphasizes several principles:

1. **Evidence provenance:** Financial observations and retrieved information should remain traceable to their sources.
2. **Deterministic calculations:** Numerical financial findings are computed independently of generated commentary.
3. **Explicit uncertainty:** Missing, ambiguous, or insufficient evidence should not be silently converted into confident conclusions.
4. **Separation of concerns:** Data retrieval, financial analysis, evidence evaluation, and narrative generation remain distinguishable stages.
5. **Reproducibility:** Research execution and evaluation artifacts support independent inspection.

## Limitations

InvestmentIntelligence is a research system, not an automated investment adviser.

The quality of its conclusions depends on data availability, source coverage, extraction accuracy, and the sufficiency of supporting evidence. LLM-generated interpretations may require human review.

Passing automated tests establishes software regression coverage; it does not independently establish equivalence to commercial investment research platforms.

## Project status

Version 1.0.0 is the initial formal public release of the integrated application.

Development continues in a separate private repository, with curated public releases.