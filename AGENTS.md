# AGENTS.md

This file applies to the entire repository.

## Product intent

`scene-port` transforms photos, videos, and live camera feeds into explorable 3D environments.

Optimize work in this order:

1. Geometric and temporal correctness
2. Reproducible results
3. Interactive performance
4. A clear user experience
5. Maintainable, well-separated code

Do not trade scene fidelity or predictable behavior for an impressive-looking demo without making the trade-off explicit.

## Repository status

The project is at an early stage. Python is currently implied by the repository configuration, but no framework, package layout, Python version, or command runner has been established yet.

- Treat checked-in configuration and documentation as the source of truth.
- Do not introduce a framework, cloud service, database, or large dependency unless the task requires it.
- When establishing a new convention, document it in the same change.
- Keep architectural choices easy to revise until requirements are proven.

## Working agreement

Before changing code:

- Read the relevant files and check the working tree for existing user changes.
- Identify the narrowest coherent change that satisfies the request.
- State any assumption that materially affects architecture, data formats, performance, or output quality.

While changing code:

- Preserve unrelated edits and avoid opportunistic refactors.
- Keep ingestion, scene reconstruction, rendering/runtime, and user-interface concerns separated.
- Prefer explicit data contracts between stages over shared mutable state.
- Make failures actionable: include the failed input or stage, but do not expose sensitive media contents.
- Add dependencies only through the project's dependency metadata, and commit the corresponding lockfile once one exists.

## Python conventions

Until more specific tooling is configured:

- Use modern Python with type hints on public interfaces.
- Prefer `pathlib.Path` for filesystem paths.
- Use small, composable functions and typed data objects for pipeline boundaries.
- Keep configuration outside business logic; do not bury device, model, or path choices in constants.
- Avoid import-time work, global model initialization, and hidden network access.
- Make randomness controllable with an explicit seed where reproducibility matters.
- Write docstrings for public APIs when behavior, units, coordinate systems, or shapes are not obvious.

Follow the formatter, linter, type checker, and test configuration in the repository once those tools are added. Do not reformat unrelated files.

## Media and 3D data rules

- Treat all input media and metadata as untrusted.
- Validate file type, dimensions, duration, frame rate, and resource limits before expensive processing.
- Preserve or deliberately normalize orientation, timestamps, color space, camera calibration, units, axis conventions, and handedness.
- Document tensor/array shapes and coordinate systems at module boundaries.
- For video and live input, keep ordering and timestamps explicit; do not assume a constant frame rate.
- Provide a CPU-safe path or a clear capability error when accelerated hardware is unavailable.
- Do not commit raw user media, generated scenes, model weights, credentials, or large binary artifacts.
- Keep test fixtures small, synthetic, redistributable, or clearly licensed.

## Testing and verification

Every behavior change should have proportional verification.

- Add focused unit tests for transforms, validation, and data contracts.
- Add integration tests at pipeline boundaries rather than relying only on end-to-end visual inspection.
- For image, video, and geometry outputs, prefer numeric assertions with documented tolerances. Use visual snapshots only when they add meaningful coverage.
- Cover malformed inputs, empty inputs, cancellation/cleanup, and unavailable hardware where relevant.
- Measure performance before making performance claims; record the input size, hardware, warm-up, and metric used.
- Run the repository's configured tests and quality checks before handing off a change. If a check cannot run, report exactly why.

## Privacy and security

- Process user media locally by default unless remote processing is an explicit product decision.
- Never add secrets or personal data to source, fixtures, logs, or error reports.
- Prevent path traversal and unsafe output overwrites.
- Bound memory, disk, and compute use for media supplied by users.
- Pin or constrain dependencies according to the project's package-management convention once established.

## Documentation

Update documentation in the same change when modifying:

- setup or development commands;
- supported inputs or outputs;
- data formats or coordinate conventions;
- hardware or model requirements;
- user-visible behavior or limitations.

Keep `README.md` focused on onboarding and product usage. Put durable technical decisions in a dedicated architecture or decision document when those files are introduced.

## Git conventions

Use a lightweight GitHub Flow adapted from the Novel-SekAI commit and branch conventions.

### Commits

- Keep each commit to one meaningful, independently understandable change.
- Separate unrelated work, broad formatting, dependency setup, refactoring, and behavior changes when practical.
- Do not leave temporary or non-running commits in a branch that is ready to merge.
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
- Make the description specific, outcome-focused, and no longer than necessary. Do not end it with a period or join unrelated outcomes in one title.
- Keep the full title within 72 characters when practical.
- Add a body when the motivation, previous behavior, trade-offs, or migration steps are not obvious.

Examples:

```text
feat: add variable-frame-rate timestamp extraction
fix: preserve portrait video orientation
docs: document scene coordinate conventions
perf: reduce duplicate frame decoding
```

### Branches

- Keep `main` runnable and releasable. Do not push directly to it.
- Create a short-lived branch from the latest `main` for each distinct task.
- Use `<category>/<description>`.
- Write descriptions in lowercase kebab-case.
- Use `feature`, `fix`, `refactor`, `docs`, `design`, `test`, `chore`, `perf`, or `hotfix` as the category.
- Do not put a person's name in a branch name.
- Avoid generic names such as `update`, `work`, `final`, or `new-branch`.

Examples:

```text
feature/live-camera-preview
fix/frame-order
docs/coordinate-system
perf/scene-loading
```

### Pull requests and merges

- Each pull request should have one purpose and target `main`.
- Use the commit-title format for the pull request title.
- Before requesting review, verify the application path, tests, lint/type checks, absence of debug code and secrets, and the lack of unrelated changes.
- Explain what changed, why it changed, how it was verified, and any remaining risk. Include screenshots only for relevant visual changes.
- Use Draft pull requests for early interface or architecture feedback when helpful.
- Prefer Squash and Merge so `main` receives one coherent conventional commit per pull request.
- Delete the task branch after merge.
- Resolve conflicts on the task branch. Use `--force-with-lease`, never plain `--force`, after a rebase; coordinate first if others share the branch.

## Definition of done

A change is complete when:

- the requested behavior works on the intended path;
- relevant tests and checks pass;
- error and cleanup paths have been considered;
- documentation reflects externally visible changes;
- no secrets, private media, generated artifacts, or unrelated edits are included;
- remaining risks or unverified assumptions are stated clearly.
