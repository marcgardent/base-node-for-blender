# Changelog

What changed for a user of Base Node for Blender, by version: the add-on, the libraries
`base-node-blender` in Python and in Rust, `<bn-view>`, the targets, the standard library, the corpus
and the site. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the
versions follow [Semantic Versioning](https://semver.org/) as [`spec/blender.md`](spec/blender.md#versions)
says. What changed in the language and its core is in the
[changelog of base-node-language](https://github.com/marcgardent/base-node-language/blob/main/CHANGELOG.md).
Versions below 1.0.0 are pre-releases: the text format can change between them.

## [Unreleased]

## [1.0.0-rc.10] - 2026-11-23

### Blender add-on

- Fixed: an unknown name given to an input is underlined where it is written, no longer on the
  input's name: `IcoSphere(radius: size)` underlines `size`, not `radius`.
- Added: the cursor on an error, or just past it, shows its message in a box under the line, as the
  suggestions are shown.
- Fixed: every new tree of a text is laid out as Arrange Nodes does, the second graph of a text as
  the first; before, only a tree with comments was.
- Fixed: a build keeps the selection of the nodes and selects nothing in a new tree. Every node came
  selected, so Arrange Nodes and Copy Selected took the whole tree.
- Changed: Paste .bn arranges the trees it builds, a group rebuilt in place too.
- Fixed: Nodes ↔ Text from the Shader Editor and back stays in the Shader Editor; it landed in
  Geometry Nodes.
- Changed: every `|>` is drawn ▷, wherever it is, a pipe just typed too; only the one the cursor is
  in, or the selection covers, shows its two characters. Before, the whole line of the cursor did,
  and so the line a failed build put the cursor on.
- Fixed: completion offers the outputs of a node written with its settings in brackets:
  `sites = DistributePointsOnFaces[POISSON](…)` then `sites.` offers `points`, `normal`, `rotation`.

### Site and documents

- Changed: the mini moon tutorial is illustrated by its phases, animated.

## [1.0.0-rc.9] - 2026-11-23

### Blender add-on

- Changed, a text needs an edit: a setting by position goes to the one enum setting of the node
  that holds its value, whatever their order, no longer to the first in Blender's order, which
  another version of Blender may change. A value two settings hold is named:
  `AlignEulerToVector[axis: X, pivot_axis: Z]`, where `AlignEulerToVector[X, pivot_axis: Z]` is
  refused (`AlignEulerToVector: X is a value of axis and of pivot_axis; name it,
  AlignEulerToVector[axis: X]`); so are `X`, `Y`, `Z` of Align Rotation to Vector, Axes to Rotation
  and Wave Texture, the spaces of Vector Transform and the color spaces of Convert Colorspace. A
  template's type by position goes to the one setting that has a value for it, else is named. Tree →
  Text already named them: the texts it wrote, the corpus among them, are the same. Completion offers
  by position only the values that go so; `setting_of` (Python and Rust) answers none for such a value.

## [1.0.0-rc.8] - 2026-11-23

### Repository

- Changed: Base Node for Blender is a repository of its own,
  https://github.com/marcgardent/base-node-for-blender, with a version of its own. It needs one
  version of the core of the language, `base-node`
  ([base-node-language](https://github.com/marcgardent/base-node-language)), its git submodule
  `core/`: `git clone --recurse-submodules`, or `make core` in a clone. 1.0.0-rc.8 needs the core
  1.0.0-rc.8.
- Changed: the site is https://blender.basenode.ludopant.com/, and so is the extension repository:
  https://blender.basenode.ludopant.com/extensions/index.json, to add in Blender (*Preferences >
  Get Extensions > Repositories*) in place of https://basenode.ludopant.com/extensions/index.json.
  https://basenode.ludopant.com/ is the site of the language.
- Changed: install from GitHub with
  `git+https://github.com/marcgardent/base-node-for-blender.git#subdirectory=python` (Python) and
  `git = "https://github.com/marcgardent/base-node-for-blender.git"` (Rust).
- Added: this changelog, with the changes of Base Node for Blender since 0.8.0.

### Libraries

- Added: the distribution `base-node-blender`, which depends on `base-node` of the version it needs,
  and adds `check`, `fmt --names` and `docs` to `base-node` through an entry point of the group
  `base_node.cli`; from a checkout, `python -m base_node_blender.cli` is that `base-node`. Its crates
  are one workspace whose one path outside it is the core's crate.
- Changed: `base_node_blender.__version__` and `STDLIB_VERSION` (Rust: `base_node_blender::VERSION`
  and `STDLIB_VERSION`) are this library's version; the core's is `base_node.__version__`.
  `base_node_blender.manifest` reads the manifest of the standard library.
- Added: a library of another destination makes its targets known to Blender's library:
  `base_node_blender.targets.add_targets(folder)` or an entry point of the group
  `base_node_blender.targets` in Python, `base_node_blender::targets::add_targets(files, bridges)` in
  Rust. The target format keeps its translators and bridges, tested with a target of the tests,
  `conformance/targets/pixels.json`.
- Changed: `base-node docs` reads the language's pages from the checkout of the core (`--core`,
  default: the one `base_node` is imported from); the reference has a page `blender.html`.
- Removed: the target `blade` (Blade's Pixel Nodes), its translator from `blender`, its bridge
  `blender_interop` and its backend tag of `<bn-view>`: they live in Blade's own sources.

### Blender add-on

- Changed: the add-on embeds the core as before; `make addon-lang` links its modules into
  `addon/lang/`, no longer in git, and the zip holds the same files.
- Changed: its website is https://blender.basenode.ludopant.com/.

### Site and documents

- Changed: the grass of the tutorial `forest_edge` is made of stalks (`stalk`, `Stalks`).
- Changed: the corpus READMEs name the version that read the libraries, 1.0.0-rc.8; the texts are the same.

## [1.0.0-rc.7] - 2026-11-22

### Tests

- Fixed: the corpus test is skipped on Python 3.10, which reads no TOML.

## [1.0.0-rc.6] - 2026-11-22

### Blender add-on

- Fixed: Tree → Text writes an enum value, a menu's item or a material that is no bare name as a
  string: `inf`, `nan`, `true` were written bare and read back as a number or a boolean, `_` as no
  value. An enum value named like a name that holds a value in the text is a string too
  (`AlignEulerToVector["X"](…)` beside an input `X`), which the parser refused bare. The editor's
  suggestions quote such a value, its escapes written, and take a word of any script.

## [1.0.0-rc.5] - 2026-11-22

### Blender add-on

- Changed, a text needs an edit: the checker refuses a value by position where the canonical form
  names the input, at the value, with the name to write: `Math: input 1 is 'Value'; write it by name,
  Math[ADD](Value: a, …)`. The texts of the standard library, the examples, the conformance cases and
  the tests give their inputs by name.
- Added: *Format* writes the inputs of the text's nodes by name, as Blender's sockets go, and *Name
  Inputs* (the text's context menu, and the button beside such an error in the sidebar) those of the
  call under the cursor, the rest of the text as it is. In a node's parentheses the suggestions are
  its inputs, `name: `, and the values only where one may go by position.
- Fixed: Tree → Text writes a value unless it is, bit for bit, the one it leaves out: a float within
  1e-6 of a default was dropped (`0.79999995` read back `0.8`, `5e-07` read back `0.0`), `-0.0` became
  `0.0`, a bound of ±3.40282e38 became the largest float, a ramp or a curve within 1e-5 of a new node's
  was left out. A value past the largest float32 is infinity, no longer an export error.
- Fixed: a flag-set setting (`mode` of Handle Type Selection and Set Handle Type) is written and built:
  `{LEFT}` read back `{LEFT, RIGHT}`.
- Fixed: the value of a Group Output's input nothing feeds is written when a new output holds another
  (Material Library VX's Ceramic: a colour of alpha 0 read back with alpha 1).
- Fixed: an unconnected Math of two numbers (`0.5 × -1`) stays a Math, where it was read `-0.5`, a Value
  node; a second Separate XYZ of one vector stays a call, where `v.x` merged it into the first.
- Fixed: a tree with no Group Output node reads with no return, and builds without one.
- Fixed: a group a module built and edited in the file since is written as a graph of the text: the
  `use` rebuilt it from the module, the edit lost. A `use` is written while the group reads as the
  module's graph built afresh.

### Tools

- Added: `base-node fmt --names` writes the inputs by name without Blender, from the sockets of the
  Blender the text promises (`@target blender@5.2-lts`), else of the newest; `make names FILES=…`
  runs it. The backends `targets/backends/blender-<x.y>.json` list, for each node, the sockets each
  setting makes, alone or with another, and Blender's identifier of a socket where it is not its key:
  `base_node_blender.backend.BackendSchema` reads them, and the checker runs without Blender on every
  text of `corpus/v1`.
- Added: the library tests compare each tree with the tree built back on Blender's data
  (`tests/tree_compare.py`) and fail on any difference but those the reference lists in "What the
  text does not carry". The corpus and the baselines are written again: strings with escapes, the
  values no longer dropped, the flag sets.

## [1.0.0-rc.4] - 2026-11-22

### Corpus

- Added: `corpus/v1/`, the node groups of the 17 third-party libraries of the tests read as `.bn` text
  by Blender 5.3, each folder under its library's license: a later version of the language must read them.

### Blender add-on

- Changed, every text needs an edit: the checker reads a node's settings from its brackets only. A
  setting by position is an enum value, which goes to the first enum setting of the node, in
  Blender's order, that holds it (`Compare[INT, EQUAL]`, `AlignEulerToVector[X, pivot_axis: Z]`);
  a template's type by position goes to the first setting that has a value for it
  (`NamedAttribute[T](name: n)`, `Switch[T](…)`). An argument in parentheses is always an input:
  `Math(a, b, operation: ADD)` is refused as any unknown input (`Math has no input 'operation'`),
  where rc.3 guessed a setting from the kind of value. The domain of a For Each zone is its setting,
  `foreach[FACE](geometry, item: f) -> { … }`; so are ramps and curves
  (`ColorRamp[color_ramp: Ramp(…)](factor: f)`), datablocks (`Object[object: "Thing"]()`), `_` and
  the values of the input nodes no literal makes (`Rotation[rotation_euler: (0.1, 0.0, 0.0)]()`).
  Errors: an unknown setting, a value no enum setting of the node holds, a setting given twice, a
  value of the wrong kind, settings on a graph, a group, a function, `repeat` or `simulate`.
- Changed: Tree → Text writes the settings in brackets, those by position first: an enum value by
  position when no other enum setting of that node holds it, else by name.
- Fixed: the Normal node of a shader or a compositor tree keeps its vector, which it holds on its
  output: `Normal[normal: (0.0, 0.7071, 0.7071)]()`. rc.3 read it back as `Normal()`, at (0, 0, 1).
- Changed: a datablock the file does not have no longer stops the build: the input or the setting
  stays empty and a warning says `missing datablock: Font "Title"`, once per datablock.
- Removed: the messages that told of a former spelling or name: a node's name of before
  (`it is now written Grid`), a zone with no arrow or `closure(…)` (`repeat takes a body after
  '->'`), a target's name of before (`'gltf' is now 'blender gltf'`). An unknown name is unknown,
  with the names it looks like. Removed too: rc.3's warning on a font of the file named
  `Bfont Regular`.
- Targets: a rule reads a setting from the brackets, by name or by position, and a translator
  renames the settings given by name; the catalogs `targets/blender/<x.y>.json` list each node's
  enum settings (`enums`) for that. The web viewer draws a node's settings from its brackets.
- Completion offers a node's settings inside its brackets (its enum values, then the names of its
  settings) and its inputs inside its parentheses; the editor colors a call and its enum values.

## [1.0.0-rc.3] - 2026-11-22

### Blender add-on

- Changed, a text of 1.0.0-rc.2 may need an edit: a datablock's input node is a call, linked or
  not, holding a datablock or none: `o = Object(object: "Thing")`,
  `ObjectInfo(object: Object(object: "Thing"))`, `Font(font: _)`. A named string is a String node,
  whatever reads it: rc.2 made `o = "Thing"` an Object node when an Object input read it first, a
  type the text did not show, and read the same node as `Object(object: "Thing")` once it fed
  nothing or held nothing.
- Changed: a named string given to a datablock input is an error that says what to write, the name
  in place or the input node: `font: "Bfont Regular", or name a Font node: t = Font(font: "Bfont
  Regular")`. Before rc.2 the input took its value and the String node stayed, linked to nothing. A
  Sound, which has no input node, comes from a graph input or its name in place.
- Added: a font of the file named `Bfont Regular` that is not Blender's own reads with a warning: the
  text names Blender's own so, and builds it back so.

## [1.0.0-rc.2] - 2026-11-22

### Blender add-on

- Fixed: Blender's own font reads as `"Bfont Regular"` whatever the file names it. A library
  appended in a session that had loaded the font brings its copy as `Bfont Regular.001`, which a
  String to Curves then wrote as `font: "Bfont Regular.001"`: the text depended on what the
  session had done before (T3D GN Presets, 2 groups, on the CI).
- Fixed: a String to Curves without a font, and a Font node without one, read as `font: _`;
  they were written as the built-in font, or as `Font(font: "None")`, which did not build.
- Fixed: a named string that a datablock input reads first, `title = "Bfont Regular"` then
  `StringToCurves(font: title)`, is a Font node named `title` (Object, Collection, Material and
  Image alike); it was a String node linked to nothing, and the name was lost. A Font, Object,
  Collection, Material or Image node made in Blender reads to such a constant.
- Fixed: a Rotation node, a 4D Vector node and an Integer Vector node keep their value:
  `Rotation(rotation_euler: (0.1, 0.0, 0.0))`, `Vector(vector: (1.0, 2.0, 3.0, 4.0))`,
  `IntegerVector(vector: (1, 2, 3))`. They were written without it (`Rotation()`) and built at zero.
- Fixed: a Menu node builds with the item it picks (`Menu(value: B)`), set once it is linked.

## [1.0.0-rc.1] - 2026-11-22

### Targets

- Changed, a text needs an edit: one target `blender`, named by the version of Blender, in place
  of `blender-geometry`, `blender-shader`, `blender-compositor` and `blender-gp`: `blender`,
  `blender@5.3`, `blender@5.2-lts`. `gltf` is a variant of it, `blender gltf`, beside two
  experimental ones, `blender eevee` and `blender cycles`. `blender@lts` and `blender@latest` are
  aliases for a command line. The names of before are unknown targets; the message says what to write.
- Changed: a variant of `blender` is tried by the inference only for a text that holds a shader.
- Added: the catalog of Blender 5.2 LTS. `blender` is now Blender 5.2 LTS and Blender 5.3: a text
  that says `blender` fits both, `blender@5.2-lts` and `blender@lts` name the LTS.
  [`spec/targets.md`](spec/targets.md#what-blender-53-has-that-blender-52-lts-has-not) lists what
  5.3 has that 5.2 has not; a text that uses it says `// @target blender@5.3`.

### Standard library

- Changed: the modules are written as a tree reads back to them now: 205 Switch calls are
  ternaries, and Mix Shader's inputs are `a` and `b`.
- Changed: `planar2d`, shape builder pick: each seed picks the region it is in, or the nearest
  within `pick_radius`; the regions no seed picks are deleted, the picked ones stay in place. It
  read the first seed only and moved the picked region away.
- Fixed: `stmap`, canvas: an odd size is no longer rounded up to an even one (65 × 33 gave
  66 × 34), which lost the first column and row of what was built on it.

### Tools

- Fixed: `<bn-view>` no longer leaves a node over a frame in a graph of many frames.
- Added: `make test-promised BLENDERS="…"` runs the Blender tests and the third-party libraries
  with each promised version of Blender; the CI runs Blender 5.2.4 LTS and 5.3.0.

### Blender extension

- Changed: the extension holds the targets of Blender only.
- Added: the warnings of a text (a deprecated graph called) are listed under its errors and
  underlined, without blocking the tree.

### Site and documents

- Changed: the repository is named `base-node-language`; its site and the extension repository are
  at `basenode.ludopant.com`, hosted and sponsored by Ludopant. The old addresses redirect, and
  keep serving the extension index.
- Added: the tutorial "SRT subtitles": a Geometry Nodes group that reads a SubRip file (`.srt`)
  and draws the cue of the scene's time (`make srt-check` builds it in Blender).
- Changed: every tutorial text names each input, as a tree reads back.
- Changed: the home page is about the open source project; what developers read (examples with
  their code, targets, the web component, Python and Rust) is on a page of its own.
- Added: a State of the Art page on node graphs as text, a sitemap and `robots.txt`.
- Added: this changelog.

## [0.13.0] - 2026-11-19

### Standard library

- Changed: the standard library is split. Eleven modules stay open source: `curves2d`, `fillet2d`,
  `grade`, `mask2d`, `math`, `merge`, `patterns2d`, `planar2d`, `qc`, `sdf2d`, `stmap`. Eleven
  modules of 0.12.0 leave it and are sold by the author as packs: `deform2d`, `hachures2d`,
  `ink2d`, `generators`, `mesh_effects`, `mesh_maps`, `grain`, `keying`, `light`, `passes`,
  `vr360`.
- Changed: each module says its manifest entry in the head of its `.bn`; `stdlib/manifest.json`
  no longer lists the modules.

### Tools

- Changed: `<bn-view>` shows the graphs of a text as tabs and its comments in the graph; its code
  scrolls only once clicked; a page chooses the tab and the view it opens on.

## [0.12.0] - 2026-11-17

### Standard library

- Added: compositor modules after Nuke: `merge`, `passes`, `grade`, `keying`, `light`, `stmap`,
  `vr360`, `mask2d`, `grain`, `qc`.
- Added: smart materials: `mesh_maps` (curvature, ambient occlusion, thickness, position, island
  and sky maps computed in Geometry Nodes), `generators` (masks from those maps), `mesh_effects`
  (chipped edges, dents, rivets, stitches, rust streaks, drips, dust).

### Blender extension

- Added: a `.bn` file dropped onto Blender offers, from the directives at its head, to install it
  as a module, import its groups, add its example, or make a mesh with its modifier.
- Added: Copy as .bn and Paste .bn: nodes copied as text, text pasted as nodes.
- Changed: the suggestions are found as Blender's Add menu search finds nodes.
- Fixed: the order of the links into a multi-input socket; a zone state with no name gives an
  error, not a crash; the size of a 2D Vector output is kept.

### Tools

- Added: `<bn-view>` shows a `.bn` text in the browser, its code and its node graph; `<bn-file>`
  shows it as a card to download.
- Added: `base-node docs` writes the reference pages of the site from the repository.

### Site and documents

- Added: a Tutorials section: Lunar ground and Mini moon.
- Added: examples written in Base Node: hydraulic erosion, Gray-Scott reaction-diffusion,
  differential growth of a closed curve.

## [0.11.0] - 2026-11-15

### Blender extension

- Added: errors are underlined while the text is typed and listed in the sidebar.
- Added: errors suggest the likely fix: `did you mean sin?`.
- Changed: building a large text is about 25 % faster.

### Tools

- Added: 567 node groups of 8 third-party libraries are read, rebuilt and evaluated in the CI.

## [0.10.0] - 2026-11-14

### Blender extension

- Added: the tree follows its text while it is typed, half a second after the last key once the
  text is valid ("Apply while typing", on by default).
- Added: the pipe `|>` shows as ▷, except on the lines being edited ("Show |> as ▷").
- Added: Arrange Nodes: links left to right, in line with their sockets, frames kept together.
- Changed: the keys follow Blender's: Alt+Z switches between a tree and its text (was Ctrl+`),
  Alt+P applies a text to its tree (was Ctrl+Enter), Ctrl+Space opens the suggestions,
  Ctrl+Shift+A formats a text and arranges the nodes. The panels show each shortcut.
- Changed: the suggestions open by themselves only when turned on.

## [0.9.0] - 2026-11-14

### Blender extension

- Added: inside a call, the prototype shows under the line, the input being written lit.
- Changed: the suggestions are coloured by kind, the call's inputs first.

## [0.8.2] - 2026-11-13

### Tools

- Added: the 17 Geometry Nodes assets of Cartesian Caramel's Everyday Nodes (CC0) are read, built
  back and evaluated by the tests.

## [0.8.1] - 2026-11-13

### Blender extension

- Changed: the extension is named "Base Node" and declares the files permission.
- Added: the standard library is bundled: `use math` works with no setup. The Module Folder of the
  preferences still comes first.

## [0.8.0] - 2026-11-13

### Blender extension

- Changed: the node tree is the only data in Blender. Ctrl+` switches a Node Editor to the tree's
  `.bn` text and back; Ctrl+Enter applies the text without leaving it. The persistent text beside
  a tree, and the sync between text and nodes, are removed.
- Added: File > Import > Base Node (.bn) builds the graphs of one or more files.
- Added: `use name` also finds `name.bn` beside the imported file and in the Module Folder of the
  preferences.

### Standard library

- Added: `planar2d`, `fillet2d`, `hachures2d`, `deform2d`.
