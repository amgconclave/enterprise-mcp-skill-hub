# Evaluation

Run deterministic local validation:

```bash
python -m app.evals.run_eval
```

Or:

```bash
make eval
make validate-skills
```

The eval prints:

- number of manifests checked
- valid manifest count
- invalid manifest rejection count
- enabled MCP tool count
- disabled skill exclusion result
- built-in skill invocation success count
- demo agent selected-skill count
- average invocation latency
- token usage
- estimated cost
- pass/fail summary

Mock mode is deterministic so CI and interviews produce stable results without paid API keys.
