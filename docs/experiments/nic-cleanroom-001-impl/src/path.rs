//! Canonical Path Pipeline — spec §6.
//!
//! Input: a path, as raw bytes or text. Output: bytes (the canonical
//! path), or rejection. Steps are frozen and mandatory in order:
//! 1. UTF-8 validate
//! 2. NFC normalize
//! 3. Separator normalize (`\` -> `/`)
//! 4. Reject absolute / drive-qualified input
//! 5. Dot-segment collapse (rejecting `..` past root)
//! 6. Emit (join with `/`, UTF-8 bytes)

use unicode_normalization::UnicodeNormalization;

/// Error raised by [`canonical_path`]. The spec only requires that
/// `expect_error` cases match by substring against the error message, so
/// each variant's `Display`-ish message embeds the exact phrase the spec
/// uses for that rejection reason (e.g. "absolute path",
/// "drive-qualified path", "escapes repo root via '..'").
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PathError(pub String);

impl std::fmt::Display for PathError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for PathError {}

/// Raw input to the canonical path pipeline: either bytes (must be
/// strictly UTF-8 decoded per step 1) or text already in memory (must be
/// checked for unpaired surrogates per step 1's text-input clause).
///
/// In Rust, a `&str`/`String` can never contain an unpaired surrogate —
/// the type system guarantees well-formed UTF-8/UTF-16-equivalent
/// content already. So the "text" input variant's surrogate check is
/// vacuously satisfied by construction; see QUESTIONS.md Q3 for the
/// reasoning on how this is reconciled with the spec's two-input-kind
/// framing.
pub enum RawPath<'a> {
    Bytes(&'a [u8]),
    Text(&'a str),
}

/// Run the full canonical path pipeline (§6) and return the canonical
/// path as UTF-8 bytes, or a [`PathError`] describing the rejection
/// reason.
pub fn canonical_path(input: RawPath<'_>) -> Result<Vec<u8>, PathError> {
    // Step 1: UTF-8 validate.
    let text: String = match input {
        RawPath::Bytes(b) => std::str::from_utf8(b)
            .map_err(|_| PathError("invalid UTF-8".to_string()))?
            .to_string(),
        RawPath::Text(s) => {
            // Rust &str is always well-formed UTF-8 already; there is no
            // way to construct an &str containing an unpaired surrogate.
            // Nothing further to validate here.
            s.to_string()
        }
    };

    // Step 2: NFC normalize.
    let text: String = text.nfc().collect();

    // Step 3: Separator normalize (backslash -> forward slash).
    let text: String = text.replace('\\', "/");

    // Step 4: Reject absolute / drive-qualified input.
    if text.starts_with('/') {
        return Err(PathError("absolute path".to_string()));
    }
    {
        // "the first /-delimited segment" — i.e. everything before the
        // first '/', or the whole string if there is no '/'.
        let first_segment = match text.find('/') {
            Some(idx) => &text[..idx],
            None => text.as_str(),
        };
        if first_segment.contains(':') {
            return Err(PathError("drive-qualified path".to_string()));
        }
    }

    // Step 5: Dot-segment collapse.
    let mut stack: Vec<&str> = Vec::new();
    for segment in text.split('/') {
        if segment.is_empty() || segment == "." {
            continue;
        } else if segment == ".." {
            if stack.is_empty() {
                return Err(PathError("escapes repo root via '..'".to_string()));
            }
            stack.pop();
        } else {
            stack.push(segment);
        }
    }

    // Step 6: Emit.
    let joined = stack.join("/");
    Ok(joined.into_bytes())
}

/// Convenience wrapper matching the corpus op signature (§11.1):
/// `canonical_path` takes `{"raw": <string>}` and returns the canonical
/// path bytes, hex-encoded. The corpus's `raw` argument is JSON string
/// type, so it is always supplied as text, not raw bytes — see
/// QUESTIONS.md Q3.
pub fn canonical_path_hex(raw: &str) -> Result<String, PathError> {
    let bytes = canonical_path(RawPath::Text(raw))?;
    Ok(hex_encode(&bytes))
}

pub(crate) fn hex_encode(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cp(s: &str) -> Result<String, PathError> {
        canonical_path(RawPath::Text(s)).map(|b| String::from_utf8(b).unwrap())
    }

    #[test]
    fn simple_relative_path_unchanged() {
        assert_eq!(cp("a/b/c").unwrap(), "a/b/c");
    }

    #[test]
    fn backslash_normalized_to_forward_slash() {
        assert_eq!(cp("a\\b\\c").unwrap(), "a/b/c");
    }

    #[test]
    fn dot_segments_collapsed() {
        assert_eq!(cp("a/./b").unwrap(), "a/b");
        assert_eq!(cp("./a/b").unwrap(), "a/b");
        assert_eq!(cp("a/b/.").unwrap(), "a/b");
    }

    #[test]
    fn double_slash_collapsed_like_empty_segment() {
        assert_eq!(cp("a//b").unwrap(), "a/b");
        assert_eq!(cp("a/b/").unwrap(), "a/b");
    }

    #[test]
    fn dotdot_pops_stack() {
        assert_eq!(cp("a/b/../c").unwrap(), "a/c");
        assert_eq!(cp("a/../b").unwrap(), "b");
    }

    #[test]
    fn dotdot_past_root_rejected() {
        let err = cp("../a").unwrap_err();
        assert!(err.0.contains("escapes repo root via '..'"));
        let err = cp("a/../../b").unwrap_err();
        assert!(err.0.contains("escapes repo root via '..'"));
    }

    #[test]
    fn dotdot_exactly_draining_stack_then_more_rejected() {
        // a/.. brings stack to empty; the next ".." must reject.
        let err = cp("a/../..").unwrap_err();
        assert!(err.0.contains("escapes repo root via '..'"));
    }

    #[test]
    fn absolute_path_rejected() {
        let err = cp("/a/b").unwrap_err();
        assert!(err.0.contains("absolute path"));
    }

    #[test]
    fn absolute_after_backslash_normalize_rejected() {
        // backslash normalization happens before the absolute check, so
        // a leading backslash counts as an absolute path too.
        let err = cp("\\a\\b").unwrap_err();
        assert!(err.0.contains("absolute path"));
    }

    #[test]
    fn drive_qualified_path_rejected() {
        let err = cp("C:/Users/x").unwrap_err();
        assert!(err.0.contains("drive-qualified path"));
    }

    #[test]
    fn drive_qualified_path_via_backslash_rejected() {
        let err = cp("C:\\Users\\x").unwrap_err();
        assert!(err.0.contains("drive-qualified path"));
    }

    #[test]
    fn colon_in_later_segment_is_fine() {
        // Only the FIRST segment is checked for ':'; a colon later is
        // not a drive qualifier per the spec text ("If the first
        // /-delimited segment contains a ':'").
        assert_eq!(cp("a/b:c").unwrap(), "a/b:c");
    }

    #[test]
    fn empty_path_yields_empty_output() {
        // Splitting "" on '/' yields one empty segment, which
        // contributes nothing, leaving an empty stack -> empty string.
        assert_eq!(cp("").unwrap(), "");
    }

    #[test]
    fn nfc_normalization_applied() {
        // "e" + combining acute accent (U+0065 U+0301) NFC-normalizes to
        // the precomposed "é" (U+00E9). Both inputs should canonicalize
        // to the identical byte sequence.
        let decomposed = "e\u{0301}.txt"; // e + combining acute
        let precomposed = "\u{00E9}.txt"; // é
        assert_eq!(cp(decomposed).unwrap(), cp(precomposed).unwrap());
    }

    #[test]
    fn single_dot_path_is_empty() {
        assert_eq!(cp(".").unwrap(), "");
    }

    #[test]
    fn single_dotdot_path_rejected() {
        let err = cp("..").unwrap_err();
        assert!(err.0.contains("escapes repo root via '..'"));
    }

    #[test]
    fn hex_helper_matches_op_contract() {
        let hex = canonical_path_hex("a/b").unwrap();
        // "a/b" -> bytes [0x61, 0x2f, 0x62] -> hex "612f62"
        assert_eq!(hex, "612f62");
    }
}
