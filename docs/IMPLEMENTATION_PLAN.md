# Robust widget API implementation plan

The migration is intentionally additive: existing VTK methods and imports stay
valid while predictable desktop-UI behavior is added in layers.

## 1. Common contract

- [x] Object names, parent/child ownership, enabled/visible state and geometry
- [x] Signals, signal blocking, deterministic close/delete, render batching
- [x] Owned VTK observer lifecycle

## 2. Input and behavior

- [x] One focused widget per interactor, Tab/Shift-Tab traversal and Escape
- [x] Exclusive text editing and mouse capture during drag interactions
- [x] Button press/release/click semantics
- [x] Slider orientation and tracking/commit semantics
- [x] List selection/activation and dock lifecycle signals
- [x] Long-running reconstruction start/finish/failure signals

## 3. Application integration

- [x] JSON-compatible state save/restore for controls and containers
- [x] Runtime theme refresh hooks
- [x] Structured logging for frequently executed paths

## 4. Package structure and assurance

- [x] Stable `controls`, `containers`, and `specialists` import surfaces
- [x] Preserve `multipanel.widgets` as a compatibility namespace
- [x] Contract tests, Linux/macOS CI, build validation and a basic example
- [x] Migrate the host application's primary UI construction to focused imports
- [x] Separate resource paths and optional dependency loading from widgets
- [x] Make scientific and icon-conversion dependencies optional and lazy
- [x] Move class implementations into their focused modules while retaining
  `multipanel.widgets` as an identity-preserving compatibility namespace

The physical split is complete. The host application exercises the focused imports and
`multipanel.widgets` now aggregates those same class objects and legacy helper
functions. Import-identity and shared-configuration tests prevent the
compatibility namespace from diverging from the implementation modules.

## Next phase

Toolkit-level services (event routing, layouts, popups, actions, the standard
widget catalogue, text editing, styling, models and tooling) are proposed in
[the Qt parity proposal](QT_PARITY_PROPOSAL.md), which includes the tracking
checklist for that work.
