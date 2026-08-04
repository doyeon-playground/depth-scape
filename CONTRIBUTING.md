# Contributing to DepthScape

DepthScape is in an early planning and baseline-evaluation stage. Small,
reproducible changes are easier to evaluate than broad rewrites.

## Before contributing

- Search existing issues before opening a new one.
- Use an issue to discuss changes that alter product scope, architecture,
  artifact formats, camera limits, model dependencies, privacy behavior, or
  supported locales.
- Never add private or copyrighted test media without redistribution rights.
- Record the source and license of external models, weights, datasets, and
  sample assets.
- Do not describe AI-generated hidden content as recovered reality.

## Development workflow

1. Create a short-lived branch from the latest `main`.
2. Keep the change focused and include documentation or tests when relevant.
3. Run the checks documented by the affected component.
4. Open a pull request describing the problem, approach, verification, and known
   limitations.

Suggested branch names:

```text
feature/depth-preview
fix/hole-mask-edge
docs/camera-limits
```

Commit titles follow `<type>: <description>` without a scope. Common types are
`feat`, `fix`, `docs`, `test`, `refactor`, `build`, and `chore`.

## Experimental depth and completion work

An experiment should state:

- the input and expected output;
- model, weight, and dependency versions;
- code and weight licenses;
- relevant hardware, precision, input size, runtime, and peak memory;
- configuration, seed, and preprocessing steps;
- output shapes, numeric ranges, and coordinate conventions;
- qualitative or quantitative observations;
- generated-region provenance; and
- known failure cases.

Do not present relative depth as metric depth. RGB inpainting experiments must
also explain how hidden depth and foreground/background ordering are handled.

## Documentation and translations

English is the source language. Korean, Japanese, Simplified Chinese, and
Spanish are supported translations. Update English first, then update or flag
affected translations according to [the i18n guide](docs/i18n.md).

Translation contributions should preserve intent rather than mirror English
word order. Keep filenames, commands, code, model identifiers, and locale tags
unchanged.

## Pull request checklist

- [ ] The change has one clear purpose.
- [ ] I documented user-visible behavior, camera limits, and failure cases.
- [ ] I verified links, commands, tests, or artifacts affected by the change.
- [ ] I documented the source and license of new external assets or weights.
- [ ] Generated content remains distinguishable from observed input.
- [ ] I updated translations or identified which ones need follow-up.
