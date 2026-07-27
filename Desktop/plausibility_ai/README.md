# Plausibility AI

Automated triage and validation commentary for financial risk model plausibility test breaches.

## Setup

```bash
python3.14 -m venv .venv
source .venv/bin/activate
poetry install
```

## Usage

### Indexing Documentation and Source Code
```bash
poetry run python -m src.cli --config src/config/config.yaml index
```

### Analyzing Plausibility Reports
```bash
poetry run python -m src.cli --config src/config/config.yaml analyze path/to/report.xlsx --output path/to/output.xlsx
```

### Running Tests
```bash
poetry run pytest
```
