# Tests

One folder per module, with the same name as in `src/splintercam/`:

```text
tests/geometry2d/unit/
tests/geometry2d/property/
tests/geometry2d/differential/
```

Tag every test with the requirement it verifies: `@pytest.mark.req("REQ-OFF-003")`. Property tests use Hypothesis. Rules: [docs/dev/06](../docs/dev/06-testing-and-quality-gates.md).
