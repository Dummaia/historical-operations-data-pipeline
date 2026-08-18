# Contributing

Thank you for considering a contribution.

## Development setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install the development dependencies:

   ```bash
   pip install -e ".[dev,postgres]"
   ```

3. Run the quality checks:

   ```bash
   ruff check .
   ruff format --check .
   pytest --cov
   ```

## Pull requests

- Keep changes focused and covered by tests.
- Do not commit credentials, corporate data, private URLs or real identifiers.
- Update the documentation when behavior or the data contract changes.
- Use clear commit messages that describe the outcome.
