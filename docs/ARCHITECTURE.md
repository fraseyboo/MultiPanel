# Package architecture

MultiPanel separates its public widgets by responsibility while retaining one
compatibility import for applications written against the original package.

## Module ownership

- `_widget_support` contains shared constants, drawing helpers, theme access,
  lazy optional-dependency access, and process-wide UI configuration.
- `input` owns interactor-level routing such as `ClickManager`.
- `controls` owns leaf controls such as buttons, sliders, text fields, and
  colour controls.
- `containers` owns panels, scrolling collections, docks, and viewport display
  controls.
- `specialists` owns scene manipulators, probes, slicing, and reconstruction
  widgets.
- `widgets` is an aggregate compatibility namespace. It contains no widget
  implementation and re-exports the exact objects from the modules above.

The intended dependency direction is shared support → controls → containers
and specialists. A container that embeds a specialist control resolves it
inside its constructor, avoiding an import-time cycle. Optional scientific and
icon conversion libraries are also resolved only when their feature is used.

## Compatibility rules

Moving an implementation must not create a second class object. For example,
`multipanel.widgets.DockPane` is `multipanel.containers.DockPane`, not a wrapper
or subclass. Shared mutable configuration is accessed through functions rather
than copied module values, so legacy setters continue to affect focused
implementations.

New code should import from the focused module. Existing `widgets` imports are
supported and can coexist with focused imports during application migration.
