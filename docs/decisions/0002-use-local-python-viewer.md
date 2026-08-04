# 0002: Use a local Python viewer

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

DepthScape originally described the bounded 2.5D viewer as a browser
application and retained video and live-camera work as deferred ideas. The
pipeline is already Python-first, processing is local by default, and the
project now deliberately targets only one landscape photo.

Maintaining a separate web application would add a second runtime, packaging
boundary, localization surface, and scene-transfer mechanism before the core
geometry and completion contracts are stable.

## Decision

Build the final interactive viewer as a local Python application. The viewer
will consume the same versioned scene artifacts as the command-line pipeline,
enforce the recorded horizontal camera bounds, and expose source, depth,
geometry, and generated-region inspection modes.

The GUI and rendering toolkit will be selected through a small measured
prototype after scene packaging is stable. This decision chooses Python, not a
specific framework.

Video reconstruction, temporal fusion, live-camera capture, and real-time SLAM
are permanently excluded from DepthScape rather than planned as later phases.

## Consequences

- Pipeline and viewer share one language and can reuse validated artifact
  readers without a network or serialization bridge.
- User images and generated scenes remain local by default.
- Desktop packaging, graphics drivers, event-loop integration, accessibility,
  and internationalization must be evaluated for the selected Python toolkit.
- The viewer must not depend on a browser, local web server, cloud account, or
  hosted asset storage.
- Any future video or live-camera project requires a separate repository and
  product decision.
