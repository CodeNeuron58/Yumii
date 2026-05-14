# How to Contribute to Yumi

First of all, thank you for your interest in contributing to Yumi! Yumi is designed to be an open and modular virtual companion.

## Getting Started
1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```
4. Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature/my-new-feature
   ```

## Development Workflow
- **Code Style:** We use `ruff` for linting and formatting. Run `ruff check .` and `ruff format .` before submitting.
- **Testing:** We use `pytest` for testing. Make sure to run `pytest tests/` and add tests for any new functionality.
- **Type Checking:** Please run `mypy src/` to ensure type safety.

## Pull Requests
- Provide a clear and descriptive title.
- Explain the changes made and the problem they solve.
- Ensure all CI checks pass.

We welcome contributions of all kinds, including new personalities, improved prompts, UI enhancements, and core backend features!
