# Builda — Initial Scaffold

Welcome to Builda — a lightweight starter scaffold that bundles a minimal frontend page and a Python backend/CLI to kick off rapid prototyping.

This repository is intended as a small, well-organized starting point for building tools that combine a simple static UI with an extensible Python backend and CLI.

## Highlights

- Minimal static frontend: a single HTML file (`index2.html`) for quick UI experiments.
- Python backend packaged with `pyproject.toml` for dependency and build management.
- Simple CLI utility and TTS helper to demonstrate core interactions.

## Quick Start

Recommended: use Poetry. Running `poetry install` will create and manage the project virtual environment for you.

1. Install dependencies with Poetry:

```bash
poetry install
```

2. Run the app with `uvicorn`:

```bash
poetry run uvicorn src.main:app --reload
```

If you prefer pip, install the package in editable mode and run the same app with `uvicorn`:

```bash
pip install -e .
uvicorn src.main:app --reload
```

## Project Structure

- `index2.html` — Minimal frontend entry for experiments.
- `Readme.md` — This file.
- `BE/` — Python backend and CLI package.
  - `pyproject.toml` — Project metadata and dependencies.
  - `src/` — Source files:
    - `main.py` — CLI entrypoint / starter runner.
    - `cli_ui.py` — Command-line user interface helpers.
    - `kokoro_tts.py` — Text-to-speech helper (example integration).
    - `test.py` — Example/test utilities.
    - `be/` — Package module (initial `__init__.py`).
    - `context_RAG/` — placeholder for context / RAG workflows.
- `tests/` — Test package placeholder.

## Usage

- Run the backend locally with reload enabled:

```bash
poetry run uvicorn src.main:app --reload
```

- Run tests (example):

```bash
python -m pytest tests
```

## Development Notes

- Keep a `.venv` or use `poetry` to ensure dependency isolation.
- Follow idiomatic packaging: keep top-level imports inside `src/` and use `uvicorn src.main:app --reload` for running the FastAPI app during development.

## Next Steps / Suggestions

- Add a simple backend HTTP server (Flask/FastAPI) for integrating `index2.html` with the Python backend.
- Add unit tests for `cli_ui.py` and `kokoro_tts.py` and enable CI (GitHub Actions) to run tests on push.
- Document environment variables, config files, and expected inputs for TTS and other integrations.

## Contributing

Contributions are welcome — open issues or PRs for feature requests, bug fixes, or documentation improvements.

## License

This scaffold is provided as-is. Add a `LICENSE` file to indicate your preferred licensing.
