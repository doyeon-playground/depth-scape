# AGENTS.md

This file applies to the entire repository.

## Product intent

`depth-scape` transforms one landscape photo into an explorable 2.5D scene. It
estimates relative depth, builds image-textured continuous geometry with cuts at
likely depth discontinuities, generates only the small hidden regions revealed
by bounded camera motion, and preserves provenance for generated content.

Optimize work in this order:

1. Truthful separation of observed and generated content
2. Geometric, depth, and layer coherence
3. Reproducible results
4. Stable interactive performance
5. A clear and accessible user experience
6. Maintainable, well-separated code

Do not trade predictable behavior or honest synthesis for an impressive-looking
demo without making the trade-off explicit.

## Repository status

The project is at an early baseline-evaluation stage. The pipeline and final
viewer are local Python software. Python 3.10 through 3.13 and the current
package layout are established, but the desktop GUI/rendering toolkit and final
scene format remain deliberately unselected.

- Treat checked-in configuration and documentation as the source of truth.
- Do not introduce a framework, cloud service, database, or large dependency
  unless the task requires it.
- Treat model names in planning documents as candidates until an experiment
  records the exact version, weight source, license, and runtime requirements.
- When establishing a new convention, document it in the same change.
- Keep architectural choices easy to revise until requirements are proven.

## Working agreement

Before changing code:

- Read the relevant files and check the working tree for existing user changes.
- Identify the narrowest coherent change that satisfies the request.
- State any assumption that materially affects architecture, data formats,
  camera limits, performance, or output quality.

While changing code:

- Preserve unrelated edits and avoid opportunistic refactors.
- Keep ingestion, depth inference, layer construction, completion, scene
  packaging, rendering, and user-interface concerns separated.
- Prefer explicit data contracts between stages over shared mutable state.
- Make failures actionable: include the failed input or stage, but do not expose
  sensitive image contents.
- Add dependencies only through the project's dependency metadata, and commit
  the corresponding lockfile once one exists.

## Python conventions

Until more specific tooling is configured:

- Use modern Python with type hints on public interfaces.
- Prefer `pathlib.Path` for filesystem paths.
- Use small, composable functions and typed data objects for pipeline boundaries.
- Keep configuration outside business logic; do not bury device, model, seed,
  threshold, or path choices in constants.
- Avoid import-time work, global model initialization, and hidden network access.
- Make randomness controllable with an explicit seed where reproducibility
  matters.
- Write docstrings for public APIs when behavior, units, coordinate systems,
  array shapes, masks, or numeric ranges are not obvious.

Follow the formatter, linter, type checker, and test configuration in the
repository once those tools are added. Do not reformat unrelated files.

## Media and 2.5D data rules

- Treat all input media and metadata as untrusted.
- Validate file type, dimensions, orientation, color space, and resource limits
  before expensive processing.
- Preserve or deliberately normalize orientation, aspect ratio, color space,
  depth range, units, axis conventions, and handedness.
- Document tensor and array shapes, numeric ranges, coordinate systems, and mask
  semantics at module boundaries.
- Keep RGB, depth, and masks pixel-aligned or record the exact transform between
  them.
- Preserve separate provenance for observed, inferred, and generated content.
- Generate color and depth coverage only for a documented camera range, and
  prevent the viewer from moving outside it.
- Never describe generated hidden regions as recovered reality.
- Provide a CPU-safe path or a clear capability error when accelerated hardware
  is unavailable.
- Do not commit raw user media, generated scenes, model weights, credentials, or
  large binary artifacts.
- Keep test fixtures small, synthetic, redistributable, or clearly licensed.

## Testing and verification

Every behavior change should have proportional verification.

- Add focused unit tests for validation, transforms, depth normalization, masks,
  camera bounds, provenance, and data contracts.
- Add integration tests at pipeline boundaries rather than relying only on
  end-to-end visual inspection.
- For image, depth, mask, and geometry outputs, prefer numeric assertions with
  documented tolerances. Use visual snapshots only when they add coverage.
- Cover malformed and empty inputs, extreme aspect ratios, thin structures,
  invalid model output, cancellation, cleanup, and unavailable hardware where
  relevant.
- Verify that the default viewpoint preserves source composition and that
  camera bounds do not reveal uncovered regions.
- Measure performance before making performance claims; record input size,
  hardware, warm-up, precision, and metric.
- Run the configured tests and quality checks before handing off a change. If a
  check cannot run, report exactly why.

## Privacy and security

- Process user images locally by default unless remote processing is an explicit
  product decision.
- Never add secrets or personal data to source, fixtures, logs, or error reports.
- Prevent path traversal and unsafe output overwrites.
- Bound memory, disk, and compute use for user-supplied media.
- Make retention and deletion behavior explicit before adding hosted processing.
- Pin or constrain dependencies according to the project's package-management
  convention once established.

## Documentation

- Defer implementation documentation to one focused pass immediately before
  merge instead of updating it throughout development.
- Do not create or update i18n documentation or translations unless the user
  explicitly requests localization work.

Update documentation in the same change when modifying:

- setup or development commands;
- supported inputs or outputs;
- artifact formats, masks, coordinate conventions, or camera limits;
- hardware, model, weight, or license requirements;
- observed-versus-generated provenance; or
- user-visible behavior and limitations.

Keep `README.md` focused on onboarding and product usage. Put durable technical
decisions in a decision document and measured model results in an experiment
document.

## Git conventions

Use a lightweight GitHub Flow adapted from the Novel-SekAI commit and branch
conventions.

### Commits

- Keep each commit to one meaningful, independently understandable change.
- Separate unrelated work, broad formatting, dependency setup, refactoring, and
  behavior changes when practical.
- Do not leave temporary or non-running commits in a branch ready to merge.
- Use this Conventional Commits-based title format:

  ```text
  <type>: <description>
  ```

- Write commit titles and bodies in English by default.
- Do not add a scope to the commit type.
- Use the following types:
  - `feat`: new user- or system-visible capability
  - `fix`: correction of broken or incorrect behavior
  - `refactor`: internal restructuring without behavior changes
  - `docs`: documentation-only work
  - `design`: visual, layout, or design-system changes without new behavior
  - `style`: formatting-only changes
  - `test`: test-only work
  - `chore`: repository, tooling, or maintenance work
  - `perf`: measured performance improvement
  - `ci`: CI/CD configuration
  - `build`: build system or dependency changes
  - `revert`: reversal of an earlier change
- Make the description specific, outcome-focused, and no longer than necessary.
  Do not end it with a period or join unrelated outcomes in one title.
- Keep the full title within 72 characters when practical.
- Add a body when the motivation, previous behavior, trade-offs, or migration
  steps are not obvious.

Examples:

```text
feat: add bounded parallax scene preview
fix: preserve thin foreground masks
docs: document generated-region provenance
perf: reduce duplicate depth preprocessing
```

### Branches

- Keep `main` runnable and releasable. Do not push directly to it.
- Create a short-lived branch from the latest `main` for each distinct task.
- Use `<category>/<description>`.
- Write descriptions in lowercase kebab-case.
- Use `feature`, `fix`, `refactor`, `docs`, `design`, `test`, `chore`, `perf`, or
  `hotfix` as the category.
- Do not put a person's name in a branch name.
- Avoid generic names such as `update`, `work`, `final`, or `new-branch`.

Examples:

```text
feature/depth-preview
fix/hole-mask-edge
docs/camera-limits
perf/scene-loading
```

### Pull requests and merges

- Each pull request should have one purpose and target `main`.
- Use the commit-title format for the pull request title.
- Before requesting review, verify the application path, tests, lint and type
  checks, absence of debug code and secrets, and lack of unrelated changes.
- Explain what changed, why it changed, how it was verified, and any remaining
  risk. Include screenshots only for relevant visual changes.
- Use Draft pull requests for early interface or architecture feedback when
  helpful.
- Prefer Squash and Merge so `main` receives one coherent conventional commit
  per pull request.
- Delete the task branch after merge.
- Resolve conflicts on the task branch. Use `--force-with-lease`, never plain
  `--force`, after a rebase; coordinate first if others share the branch.

## Definition of done

A change is complete when:

- the requested behavior works on the intended path;
- relevant tests and checks pass;
- error and cleanup paths have been considered;
- documentation reflects externally visible changes;
- generated content remains disclosed and camera bounds remain enforced;
- no secrets, private media, model weights, generated artifacts, or unrelated
  edits are included; and
- remaining risks or unverified assumptions are stated clearly.
