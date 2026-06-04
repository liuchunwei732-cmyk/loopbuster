# Contributing to LoopBuster

## Development Setup

```bash
git clone https://github.com/liuchunwei732-cmyk/loopbuster.git
cd loopbuster
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/
```

## Linting

```bash
ruff check src/
```

## Submitting Changes

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-change`)
3. Make your changes
4. Run tests and linting
5. Commit with a clear message
6. Open a Pull Request

## Commit Convention

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code restructuring
- `test:` test additions or fixes
- `chore:` maintenance

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
