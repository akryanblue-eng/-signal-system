//! Canonical JSON encoding per spec §3.
//!
//! `canon_json(value)` is defined recursively over a JSON value model.
//! We use a hand-rolled `Value` enum (rather than relying on any
//! third-party "canonical JSON" crate) so that every formatting rule in
//! §3 is implemented explicitly from the spec text:
//!
//! - null -> `null`
//! - bool -> `true` / `false`
//! - integer -> base-10 ASCII digits, no leading zeros, no decimal point
//! - string -> JSON string literal; `\`, `"`, and control chars (U+0000-001F)
//!   escaped per the JSON grammar; non-ASCII (> U+007F) emitted literally
//!   as UTF-8 bytes, never `\uXXXX`-escaped
//! - array -> `[` + comma-joined elements (no spaces) + `]`
//! - object -> keys sorted by UTF-16 code-unit order, then
//!   `{"key":value,...}` (no space after `:` or `,`)
//!
//! Non-integer / non-finite numbers are explicitly out of scope per the
//! spec ("are not defined") since they never appear in any value this
//! spec hashes; we represent numbers only as `i64` in our `Value` model
//! (see QUESTIONS.md for the chosen integer width/representation).

/// A JSON value restricted to what this spec ever needs to canon-encode:
/// null, bool, integer, string, array, object. There is deliberately no
/// floating point variant.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Str(String),
    Arr(Vec<Value>),
    /// Object preserves insertion order in a Vec of pairs; canon_json
    /// re-sorts keys at encode time per spec, so insertion order here is
    /// irrelevant to the final encoding but is kept for fidelity when
    /// round-tripping a loaded document (e.g. the registry, §10, which is
    /// hashed "exactly as loaded" — see QUESTIONS.md).
    Obj(Vec<(String, Value)>),
}

impl Value {
    pub fn str<S: Into<String>>(s: S) -> Value {
        Value::Str(s.into())
    }

    pub fn obj(pairs: Vec<(&str, Value)>) -> Value {
        Value::Obj(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
    }

    pub fn arr(items: Vec<Value>) -> Value {
        Value::Arr(items)
    }
}

/// Encode `value` as canonical JSON bytes per spec §3.
pub fn canon_json(value: &Value) -> Vec<u8> {
    let mut out = Vec::new();
    encode(value, &mut out);
    out
}

/// Convenience: canonical JSON as a UTF-8 `String`.
pub fn canon_json_string(value: &Value) -> String {
    // canon_json always produces valid UTF-8 (it's built from UTF-8
    // strings and ASCII punctuation), so this cannot fail.
    String::from_utf8(canon_json(value)).expect("canon_json output must be valid UTF-8")
}

fn encode(value: &Value, out: &mut Vec<u8>) {
    match value {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(true) => out.extend_from_slice(b"true"),
        Value::Bool(false) => out.extend_from_slice(b"false"),
        Value::Int(i) => {
            // Base-10 ASCII digits, no leading zeros, no decimal point.
            // Rust's default i64 Display already satisfies this: it
            // prints "0" for zero, a leading '-' for negatives, and never
            // pads with zeros. (See QUESTIONS.md re: negative integers.)
            out.extend_from_slice(i.to_string().as_bytes());
        }
        Value::Str(s) => encode_string(s, out),
        Value::Arr(items) => {
            out.push(b'[');
            for (idx, item) in items.iter().enumerate() {
                if idx > 0 {
                    out.push(b',');
                }
                encode(item, out);
            }
            out.push(b']');
        }
        Value::Obj(pairs) => {
            // Keys sorted by ordinary string comparison (UTF-16 code-unit
            // order). We sort by collecting UTF-16 code units, which is
            // what "UTF-16 code-unit order" demands rather than Rust's
            // native UTF-8 byte / char (codepoint) ordering — these differ
            // for codepoints >= U+10000 vs. those in U+E000..U+FFFF etc.
            // See QUESTIONS.md for the analysis of why UTF-8 byte order
            // is NOT always equivalent to UTF-16 code-unit order.
            // We sort by (key_as_utf16, original_index) rather than into
            // a map keyed solely by the UTF-16 encoding, because a map
            // would silently drop duplicate keys. The spec's §9 "exactly
            // these N keys" model assumes well-formed unique keys, but a
            // loaded document (e.g. registry, §10) could in principle
            // contain duplicate keys before we get here; sorting
            // preserves duplicates faithfully and stably instead of
            // silently discarding one.
            let mut keyed: Vec<(Vec<u16>, usize)> = pairs
                .iter()
                .enumerate()
                .map(|(i, (k, _))| (k.encode_utf16().collect::<Vec<u16>>(), i))
                .collect();
            keyed.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
            out.push(b'{');
            for (idx, (_, orig_i)) in keyed.iter().enumerate() {
                if idx > 0 {
                    out.push(b',');
                }
                let (k, v) = &pairs[*orig_i];
                encode_string(k, out);
                out.push(b':');
                encode(v, out);
            }
            out.push(b'}');
        }
    }
}

/// Encode a Rust `String` as a JSON string literal per spec §3's string
/// rule: `\`, `"`, and control characters (U+0000-U+001F) are escaped per
/// the JSON grammar; everything above U+007F is emitted literally as
/// UTF-8 bytes (never `\uXXXX`-escaped).
fn encode_string(s: &str, out: &mut Vec<u8>) {
    out.push(b'"');
    for c in s.chars() {
        match c {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            // JSON grammar's named short escapes for control characters
            // that have one (RFC 8259 §7). All other control characters
            // get generic \u00XX.
            '\u{0008}' => out.extend_from_slice(b"\\b"),
            '\u{000C}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            c if (c as u32) <= 0x1F => {
                out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes());
            }
            // Everything else, including all non-ASCII (> U+007F),
            // emitted literally as UTF-8 bytes.
            c => {
                let mut buf = [0u8; 4];
                let encoded = c.encode_utf8(&mut buf);
                out.extend_from_slice(encoded.as_bytes());
            }
        }
    }
    out.push(b'"');
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn null_bool_int() {
        assert_eq!(canon_json_string(&Value::Null), "null");
        assert_eq!(canon_json_string(&Value::Bool(true)), "true");
        assert_eq!(canon_json_string(&Value::Bool(false)), "false");
        assert_eq!(canon_json_string(&Value::Int(0)), "0");
        assert_eq!(canon_json_string(&Value::Int(42)), "42");
        assert_eq!(canon_json_string(&Value::Int(-7)), "-7");
    }

    #[test]
    fn string_basic_escapes() {
        assert_eq!(canon_json_string(&Value::str("hello")), "\"hello\"");
        assert_eq!(canon_json_string(&Value::str("a\"b")), "\"a\\\"b\"");
        assert_eq!(canon_json_string(&Value::str("a\\b")), "\"a\\\\b\"");
        assert_eq!(canon_json_string(&Value::str("a\nb")), "\"a\\nb\"");
        assert_eq!(canon_json_string(&Value::str("a\tb")), "\"a\\tb\"");
        assert_eq!(canon_json_string(&Value::str("a\rb")), "\"a\\rb\"");
        // generic control char with no named escape
        assert_eq!(
            canon_json_string(&Value::str("a\u{0001}b")),
            "\"a\\u0001b\""
        );
        assert_eq!(canon_json_string(&Value::str("a\u{0008}b")), "\"a\\bb\"");
        assert_eq!(canon_json_string(&Value::str("a\u{000C}b")), "\"a\\fb\"");
    }

    #[test]
    fn string_non_ascii_literal_utf8() {
        // U+00E9 (é) is > U+007F: must appear literally as UTF-8 bytes,
        // not as é.
        let s = "café";
        let out = canon_json(&Value::str(s));
        let expected = "\"café\"".as_bytes().to_vec();
        assert_eq!(out, expected);
        // Sanity: it must NOT contain the substring é or é.
        let as_str = String::from_utf8(out).unwrap();
        assert!(!as_str.contains("\\u00e9"));
        assert!(!as_str.contains("\\u00E9"));
    }

    #[test]
    fn string_emoji_above_bmp_literal_utf8() {
        // U+1F600 GRINNING FACE is above the Basic Multilingual Plane;
        // confirm it's emitted as literal UTF-8, not as a \uXXXX surrogate
        // pair escape.
        let s = "\u{1F600}";
        let out = canon_json_string(&Value::str(s));
        assert_eq!(out, "\"\u{1F600}\"");
    }

    #[test]
    fn array_no_spaces() {
        let v = Value::arr(vec![Value::Int(1), Value::Int(2), Value::Int(3)]);
        assert_eq!(canon_json_string(&v), "[1,2,3]");
        assert_eq!(canon_json_string(&Value::arr(vec![])), "[]");
    }

    #[test]
    fn object_keys_sorted_no_spaces() {
        let v = Value::obj(vec![
            ("b", Value::Int(2)),
            ("a", Value::Int(1)),
            ("c", Value::Int(3)),
        ]);
        assert_eq!(canon_json_string(&v), "{\"a\":1,\"b\":2,\"c\":3}");
    }

    #[test]
    fn object_empty() {
        assert_eq!(canon_json_string(&Value::Obj(vec![])), "{}");
    }

    #[test]
    fn nested_structure() {
        let v = Value::obj(vec![
            ("to", Value::str("B")),
            ("from", Value::str("A")),
            ("type", Value::str("IMPORTS")),
        ]);
        // Sorted keys: from, to, type
        assert_eq!(
            canon_json_string(&v),
            "{\"from\":\"A\",\"to\":\"B\",\"type\":\"IMPORTS\"}"
        );
    }

    #[test]
    fn utf16_key_ordering_surrogate_vs_bmp() {
        // A key containing a codepoint above U+FFFF (encoded as a UTF-16
        // surrogate pair, code units in 0xD800-0xDFFF range) must sort
        // AFTER a key containing a BMP character like U+FFFD, because
        // surrogate code units (0xD800+) are numerically greater than
        // 0xFFFD's... wait: 0xFFFD > 0xD800. Let's pick codepoints that
        // clearly demonstrate UTF-16 code-unit order: compare a key with
        // U+E000 (BMP, code unit 0xE000) against a key whose first
        // character is U+10000 (surrogate pair: high surrogate 0xD800,
        // low surrogate 0xDC00). Since 0xD800 < 0xE000, the U+10000 key
        // sorts FIRST in UTF-16 code-unit order, even though as a raw
        // Unicode scalar value U+10000 > U+E000.
        let key_high_bmp = "\u{E000}x";
        let key_supplementary = "\u{10000}x";
        let v = Value::obj(vec![
            (key_high_bmp, Value::Int(1)),
            (key_supplementary, Value::Int(2)),
        ]);
        let encoded = canon_json_string(&v);
        // supplementary-plane key must come first
        let pos_supp = encoded.find(key_supplementary).unwrap();
        let pos_bmp = encoded.find(key_high_bmp).unwrap();
        assert!(
            pos_supp < pos_bmp,
            "UTF-16 code-unit ordering requires the surrogate-pair key to sort before U+E000"
        );
    }

    #[test]
    fn duplicate_keys_preserved_stable_order() {
        // Not expected in well-formed input, but the encoder shouldn't
        // panic or silently drop one; verify stable behavior.
        let v = Value::obj(vec![("a", Value::Int(1)), ("a", Value::Int(2))]);
        let encoded = canon_json_string(&v);
        assert_eq!(encoded, "{\"a\":1,\"a\":2}");
    }
}
