//! Base Node for Blender: what the core (`base-node`, which reads a text and names no destination)
//! leaves to a host. The targets a text is checked against or translated to (`targets/`), the
//! standard library (`stdlib/`), and the head of a file as the add-on reads it.

/// The version of Base Node for Blender: of this crate, the standard library and the add-on, as
/// Cargo.toml says it. The core's is `base_node::VERSION`, the one the workspace needs.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
/// The version of the standard library (`stdlib_version` of stdlib/manifest.json): this crate's.
pub const STDLIB_VERSION: &str = VERSION;

pub mod header;
pub mod stdlib;
pub mod targets;
pub mod zones;

pub use header::{header, header_of, Header};
pub use targets::{
    check_against, check_target, check_target_with, check_targets, check_targets_with, infer,
    infer_with, inferred_names, load_target, promise_names, promise_refusal, setting_of,
    target_names, translate, translation_issues, variant_names, Inference, Issue, Target,
    UnknownTarget,
};
