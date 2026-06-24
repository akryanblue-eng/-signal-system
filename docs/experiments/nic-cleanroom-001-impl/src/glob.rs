//! Glob Language — spec §5.
//!
//! Grammar: exactly three operators: `*`, `?`, `**`. No `[...]`, `{...}`,
//! `!` permitted — a pattern containing any of those is rejected outright
//! (fail-closed).
//!
//! - `?` matches exactly one non-`/` character.
//! - `*` matches zero or more non-`/` characters (does not cross a
//!   path-segment boundary).
//! - `**` occupying an entire path segment matches zero or more complete
//!   path segments (including across `/`). `**` elsewhere within a
//!   segment (e.g. `foo**bar` or `foo*bar`) is ordinary single-segment
//!   behavior — only a segment that is *exactly* `**` gets
//!   directory-crossing semantics.
//!
//! Matching is a full-string anchored, codepoint-for-codepoint,
//! case-sensitive match against the canonical path.

/// Error raised when a pattern contains disallowed syntax.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GlobError(pub String);

impl std::fmt::Display for GlobError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for GlobError {}

/// Validate that `pattern` contains none of the disallowed characters
/// `[ ] { } !`. Returns an error fail-closed if any are present.
fn reject_disallowed_syntax(pattern: &str) -> Result<(), GlobError> {
    if pattern.contains(['[', ']', '{', '}', '!']) {
        return Err(GlobError(
            "pattern contains disallowed glob syntax ([, ], {, }, or !)".to_string(),
        ));
    }
    Ok(())
}

/// Match `pattern` against `path` per spec §5. Returns `Ok(bool)` for a
/// syntactically valid pattern, or `Err(GlobError)` if the pattern uses
/// disallowed syntax.
pub fn glob_match(pattern: &str, path: &str) -> Result<bool, GlobError> {
    reject_disallowed_syntax(pattern)?;

    // Split both pattern and path into path segments on '/'. We match
    // segment-sequences recursively: a plain segment matches exactly one
    // path segment via single-segment wildcard rules (`*`, `?`); a `**`
    // segment matches zero or more path segments.
    let pattern_segments: Vec<&str> = pattern.split('/').collect();
    let path_segments: Vec<&str> = path.split('/').collect();

    Ok(match_segments(&pattern_segments, &path_segments))
}

/// Recursively match a sequence of pattern segments against a sequence
/// of path segments.
fn match_segments(pat_segs: &[&str], path_segs: &[&str]) -> bool {
    match pat_segs.first() {
        None => path_segs.is_empty(),
        Some(&"**") => {
            // ** as a whole segment: matches zero or more complete path
            // segments. Try consuming 0, 1, 2, ... path segments before
            // continuing to match the rest of the pattern.
            for consume in 0..=path_segs.len() {
                if match_segments(&pat_segs[1..], &path_segs[consume..]) {
                    return true;
                }
            }
            false
        }
        Some(first_pat) => {
            // Ordinary segment (possibly containing * and/or ?): must
            // match exactly one path segment.
            match path_segs.first() {
                None => false,
                Some(first_path) => {
                    segment_matches(first_pat, first_path)
                        && match_segments(&pat_segs[1..], &path_segs[1..])
                }
            }
        }
    }
}

/// Match a single non-`**`-whole-segment pattern fragment (which may
/// contain `*` and `?` wildcards, including a literal `**` substring
/// that is NOT the entire segment, e.g. `foo**bar`, which per spec is
/// "ordinary single-segment operator" behavior — each `*` within still
/// means "zero or more non-/ chars" individually) against exactly one
/// path segment. Both are matched codepoint-for-codepoint (i.e. by
/// Unicode scalar value / `char`), case-sensitive.
///
/// This is a classic wildcard matcher restricted to `*` and `?` (no
/// character classes), implemented via a small dynamic-programming
/// table over (pattern_chars, segment_chars) since segments never
/// contain `/`, so there is no cross-segment recursion needed here.
fn segment_matches(pat: &str, seg: &str) -> bool {
    let pat_chars: Vec<char> = pat.chars().collect();
    let seg_chars: Vec<char> = seg.chars().collect();
    let (p_len, s_len) = (pat_chars.len(), seg_chars.len());

    // dp[i][j] = true if pat_chars[..i] matches seg_chars[..j]
    let mut dp = vec![vec![false; s_len + 1]; p_len + 1];
    dp[0][0] = true;
    for i in 1..=p_len {
        if pat_chars[i - 1] == '*' {
            dp[i][0] = dp[i - 1][0];
        }
    }
    for i in 1..=p_len {
        for j in 1..=s_len {
            dp[i][j] = match pat_chars[i - 1] {
                '*' => dp[i - 1][j] || dp[i][j - 1],
                '?' => dp[i - 1][j - 1],
                c => dp[i - 1][j - 1] && c == seg_chars[j - 1],
            };
        }
    }
    dp[p_len][s_len]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn m(pattern: &str, path: &str) -> bool {
        glob_match(pattern, path).expect("pattern should be valid")
    }

    #[test]
    fn literal_exact_match() {
        assert!(m("a/b/c", "a/b/c"));
        assert!(!m("a/b/c", "a/b/d"));
    }

    #[test]
    fn question_mark_single_char() {
        assert!(m("a?c", "abc"));
        assert!(!m("a?c", "ac")); // ? requires exactly one char
        assert!(!m("a?c", "abbc"));
    }

    #[test]
    fn question_mark_does_not_cross_segment() {
        assert!(!m("a?c", "a/c"));
    }

    #[test]
    fn star_zero_or_more_within_segment() {
        assert!(m("a*c", "ac"));
        assert!(m("a*c", "abc"));
        assert!(m("a*c", "abbbbc"));
        assert!(!m("a*c", "a/c")); // * does not cross /
    }

    #[test]
    fn star_does_not_cross_segment_boundary() {
        assert!(!m("*", "a/b"));
        assert!(m("*", "ab"));
        assert!(m("*", ""));
    }

    #[test]
    fn double_star_whole_pattern_matches_anything() {
        assert!(m("**", ""));
        assert!(m("**", "a"));
        assert!(m("**", "a/b/c"));
    }

    #[test]
    fn double_star_leading_segment() {
        assert!(m("**/*.py", "c.py"));
        assert!(m("**/*.py", "a/b/c.py"));
        assert!(m("**/*.py", "a/c.py"));
        assert!(!m("**/*.py", "c.txt"));
    }

    #[test]
    fn double_star_trailing_segment() {
        assert!(m("a/**", "a"));
        assert!(m("a/**", "a/b/c"));
        assert!(m("a/**", "a/b"));
        assert!(!m("a/**", "b"));
    }

    #[test]
    fn double_star_middle_segment() {
        assert!(m("a/**/c", "a/c"));
        assert!(m("a/**/c", "a/x/y/c"));
        assert!(m("a/**/c", "a/x/c"));
        assert!(!m("a/**/c", "a/x/y"));
    }

    #[test]
    fn star_within_segment_alongside_other_chars_is_ordinary() {
        // "foo*bar" - the * here is the ordinary single-segment operator,
        // not directory-crossing, even though the literal substring
        // looks similar in spirit to **.
        assert!(m("foo*bar", "foobar"));
        assert!(m("foo*bar", "fooXXXbar"));
        assert!(!m("foo*bar", "foo/bar"));
    }

    #[test]
    fn literal_double_star_substring_within_larger_segment_is_ordinary() {
        // "foo**bar" is NOT a segment consisting of exactly "**", so it
        // does not get directory-crossing behavior; each '*' acts as the
        // ordinary single-segment wildcard (zero-or-more non-/ chars).
        assert!(m("foo**bar", "foobar"));
        assert!(m("foo**bar", "fooXbar"));
        assert!(m("foo**bar", "fooXYbar"));
        assert!(!m("foo**bar", "foo/bar"));
    }

    #[test]
    fn disallowed_syntax_rejected() {
        for bad in ["[abc]", "{a,b}", "a!b", "a[b]c", "{x}"] {
            let result = glob_match(bad, "anything");
            assert!(result.is_err(), "pattern {:?} should be rejected", bad);
        }
    }

    #[test]
    fn case_sensitive_match() {
        assert!(!m("ABC", "abc"));
        assert!(m("ABC", "ABC"));
    }

    #[test]
    fn anchored_full_string_match() {
        // No partial/substring matching - "bc" must not match within "abcd"
        assert!(!m("bc", "abcd"));
        assert!(!m("b*", "abcd"));
    }

    #[test]
    fn empty_pattern_matches_only_empty_path() {
        assert!(m("", ""));
        assert!(!m("", "a"));
    }

    #[test]
    fn multiple_double_star_segments() {
        assert!(m("**/a/**", "a"));
        assert!(m("**/a/**", "x/a/y"));
        assert!(m("**/a/**", "a/y"));
        assert!(m("**/a/**", "x/a"));
    }

    #[test]
    fn codepoint_for_codepoint_unicode_match() {
        assert!(m("café", "café"));
        assert!(!m("café", "cafe"));
    }

    #[test]
    fn literal_double_star_path_segment_matched_only_via_wildcard() {
        // See QUESTIONS.md Q6: a path segment that is literally "**" can
        // only be matched by the directory-crossing ** wildcard (or by
        // an ordinary single-segment wildcard pattern like "*" or "?*"),
        // never by attempting to write "**" as a "literal" pattern
        // segment - that spelling is always interpreted as the wildcard.
        assert!(m("**", "**")); // whole-pattern ** matches anything, incl. "**"
        assert!(m("a/**/b", "a/**/b")); // middle ** wildcard can match a literal "**" segment
        assert!(m("a/*/b", "a/**/b")); // ordinary * matches the 2-char segment "**"
    }
}
