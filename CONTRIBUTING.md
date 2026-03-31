# Contributing to Legal Format Engine

Thank you for your interest in contributing to the Legal Format Engine.

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Install development dependencies: `pip install -e ".[dev]"`
4. Make your changes
5. Run tests: `pytest tests/`
6. Commit with a clear message
7. Open a pull request

## Development Setup

```bash
git clone https://github.com/anchor-software-lab/legal-format-engine.git
cd legal-format-engine
pip install -e ".[dev]"
pytest tests/
```

## Code Style

- Follow PEP 8
- Use type hints for function signatures
- Write tests for new functionality
- Keep the `src` layout — all source code goes in `src/legal_format_engine/`

## Pull Request Guidelines

- Keep PRs focused on a single change
- Include tests for new features or bug fixes
- Update documentation if behavior changes
- Fill out the PR template

## Reporting Issues

Use GitHub Issues with the provided templates for bug reports and feature
requests.

## License

By contributing, you agree that your contributions will be licensed under
the MIT License.
