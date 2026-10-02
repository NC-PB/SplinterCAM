# Test support

Helpers shared by several test files: oracles that check results and Hypothesis strategies that generate inputs. pytest puts this folder on the import path (`pythonpath` in `pyproject.toml`), so a test imports them by module name, for example `from geometry2d_checks import distance_to_boundary`.

- One file per module and kind, named `<module>_checks.py` or `<module>_strategies.py`.
- No tests here, and nothing in `src/` imports from here.
