# Contributing to ScenePort

ScenePort is in an early planning and prototyping stage. Small, reproducible
changes are easier to evaluate than broad rewrites.

## Before contributing

- Search existing issues before opening a new one.
- Use an issue to discuss changes that alter product scope, architecture,
  artifact formats, model dependencies, privacy behavior, or supported locales.
- Never add private or copyrighted test media without redistribution rights.
- Record the source and license of external models, weights, datasets, and
  sample assets.

## Development workflow

1. Create a branch from `main`.
2. Keep the change focused and include documentation or tests when relevant.
3. Run the checks documented by the affected component.
4. Open a pull request describing the problem, approach, verification, and any
   known limitations.

Suggested branch names:

```text
feat/photo-depth-preview
fix/viewer-camera-reset
docs/update-photo-scope
```

Suggested commit prefixes are `feat`, `fix`, `docs`, `test`, `refactor`,
`build`, and `chore`.

## Experimental reconstruction work

An experiment should state:

- the input and expected output;
- model and dependency versions;
- relevant hardware and runtime information;
- configuration and preprocessing steps;
- qualitative or quantitative observations;
- known failure cases; and
- license implications.

Do not present single-image inferred depth as measured geometry.

## Documentation and translations

English is the source language. Korean, Japanese, Simplified Chinese, and
Spanish are supported translations. Update English first, then update or flag
affected translations according to [the i18n guide](docs/i18n.md).

Translation contributions should preserve intent rather than mirror English
word order. Keep filenames, commands, code, and locale identifiers unchanged.

## Pull request checklist

- [ ] The change has one clear purpose.
- [ ] I documented user-visible behavior and limitations.
- [ ] I verified links, commands, or tests affected by the change.
- [ ] I documented the source and license of new external assets.
- [ ] I updated translations or identified which ones need follow-up.
