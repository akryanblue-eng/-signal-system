// Thin re-export for backward compatibility with integration tests.
// The canonical implementation lives in schema::load_schemas_from_str.
pub use crate::schema::{load_schemas_from_path, load_schemas_from_str};
