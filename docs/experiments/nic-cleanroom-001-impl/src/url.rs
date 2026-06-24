//! ExternalResource URL Canonicalization — spec §7.
//!
//! Input: a URL string in
//! `scheme://[userinfo@]host[:port][/path][?query][#fragment]` generic-URI
//! form. Output: the canonical URL string.
//!
//! Rules:
//! - scheme: lowercase
//! - host: lowercase
//! - port: dropped if it equals the scheme's default port (http->80,
//!   https->443); kept verbatim otherwise
//! - userinfo: preserved verbatim (not case-folded)
//! - path: dot-segment normalized per §7.1 (lexical only, no repo-root
//!   rejection)
//! - percent-encoding: never decoded/re-encoded; only the hex digits of
//!   an existing `%XX` are uppercased
//! - fragment: dropped entirely
//! - reassembly: omit `?` if query empty; omit `//` if no authority

/// Error raised when a URL cannot be parsed per the generic-URI grammar
/// this spec assumes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UrlError(pub String);

impl std::fmt::Display for UrlError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for UrlError {}

/// Components of a parsed generic URI, per §7's grammar.
struct ParsedUrl<'a> {
    scheme: &'a str,
    /// Raw authority text (userinfo/host/port), if `//` was present.
    /// `None` means there was no authority component to render at all.
    authority: Option<&'a str>,
    path: &'a str,
    query: Option<&'a str>,
    // fragment is parsed but immediately discarded (never stored) since
    // §7 always drops it; we don't even keep a field for it.
}

/// Split `raw_url` into scheme, optional authority, path, optional query,
/// per §7's grammar: `scheme:`, then -- if followed by `//` -- an
/// authority running up to the next `/`, `?`, or `#`, then path, then
/// optional `?query`, then optional `#fragment` (fragment is dropped at
/// parse time since it's never part of the canonical form).
fn parse_url(raw_url: &str) -> Result<ParsedUrl<'_>, UrlError> {
    // scheme: everything up to the first ':'.
    let colon_idx = raw_url
        .find(':')
        .ok_or_else(|| UrlError("missing ':' after scheme".to_string()))?;
    let scheme = &raw_url[..colon_idx];
    if scheme.is_empty() {
        return Err(UrlError("empty scheme".to_string()));
    }
    let rest = &raw_url[colon_idx + 1..];

    // Authority: present iff rest starts with "//".
    let (authority, after_authority) = if let Some(stripped) = rest.strip_prefix("//") {
        // authority runs up to the next '/', '?', or '#' (or end of string)
        let end = stripped.find(['/', '?', '#']).unwrap_or(stripped.len());
        (Some(&stripped[..end]), &stripped[end..])
    } else {
        (None, rest)
    };

    // Fragment: drop everything from the first '#' onward (in whatever
    // remains after authority), BEFORE splitting off the query, since
    // fragment is always the last grammar component.
    let without_fragment = match after_authority.find('#') {
        Some(idx) => &after_authority[..idx],
        None => after_authority,
    };

    // Query: split off at first '?' in the fragment-stripped remainder.
    let (path, query) = match without_fragment.find('?') {
        Some(idx) => (&without_fragment[..idx], Some(&without_fragment[idx + 1..])),
        None => (without_fragment, None),
    };

    Ok(ParsedUrl {
        scheme,
        authority,
        path,
        query,
    })
}

/// Default port for a scheme, per §7 ("http -> 80, https -> 443"). No
/// other scheme has a defined default port under this spec.
fn default_port(scheme_lower: &str) -> Option<u32> {
    match scheme_lower {
        "http" => Some(80),
        "https" => Some(443),
        _ => None,
    }
}

/// Canonicalize the authority component: lowercase host, preserve
/// userinfo verbatim, drop port if it equals the scheme's default.
fn canonicalize_authority(authority: &str, scheme_lower: &str) -> String {
    // Split off userinfo (everything before the last '@' -- per generic
    // URI grammar there is at most one '@' delimiting userinfo from
    // host[:port]; see QUESTIONS.md for the chosen rule on multiple '@').
    let (userinfo, host_port) = match authority.rfind('@') {
        Some(idx) => (Some(&authority[..idx]), &authority[idx + 1..]),
        None => (None, authority),
    };

    // Split host from port. IPv6 literals would be bracketed
    // ([::1]:8080); see QUESTIONS.md for how this is handled.
    let (host, port) = split_host_port(host_port);

    let host_lower = host.to_lowercase();

    let mut out = String::new();
    if let Some(ui) = userinfo {
        out.push_str(ui);
        out.push('@');
    }
    out.push_str(&host_lower);
    if let Some(p) = port {
        let keep = match p.parse::<u32>() {
            Ok(p_num) => Some(p_num) != default_port(scheme_lower),
            // A non-numeric port is kept verbatim: we don't know it's
            // "the default port" so the safe, literal reading is to
            // keep it (see QUESTIONS.md).
            Err(_) => true,
        };
        if keep {
            out.push(':');
            out.push_str(p);
        }
    }
    out
}

/// Split a `host[:port]` string into `(host, Some(port))` or
/// `(host, None)`. Handles bracketed IPv6 literals (`[::1]:8080`) by
/// treating the bracketed portion as an opaque host token.
fn split_host_port(host_port: &str) -> (&str, Option<&str>) {
    if host_port.starts_with('[') {
        if let Some(close) = host_port.find(']') {
            let host = &host_port[..=close];
            let rest = &host_port[close + 1..];
            if let Some(port) = rest.strip_prefix(':') {
                return (host, Some(port));
            }
            return (host, None);
        }
    }
    match host_port.rfind(':') {
        Some(idx) => (&host_port[..idx], Some(&host_port[idx + 1..])),
        None => (host_port, None),
    }
}

/// Path dot-segment normalization per §7.1.
fn normalize_url_path(path: &str) -> String {
    let leading_slash = path.starts_with('/');
    let mut stack: Vec<&str> = Vec::new();
    for segment in path.split('/') {
        if segment == "." {
            continue;
        } else if segment == ".." {
            if !stack.is_empty() && *stack.last().unwrap() != ".." {
                stack.pop();
            } else {
                stack.push("..");
            }
        } else {
            stack.push(segment);
        }
    }
    let joined = stack.join("/");
    if leading_slash && !joined.starts_with('/') {
        format!("/{}", joined)
    } else {
        joined
    }
}

/// Uppercase the hex digits of every `%XX` percent-encoded octet in `s`,
/// without decoding or re-encoding anything else. Any literal `%` not
/// followed by two hex digits is passed through unchanged (see
/// QUESTIONS.md for malformed-percent-encoding handling).
fn normalize_percent_encoding(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = String::with_capacity(s.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() && is_hex(bytes[i + 1]) && is_hex(bytes[i + 2]) {
            out.push('%');
            out.push((bytes[i + 1] as char).to_ascii_uppercase());
            out.push((bytes[i + 2] as char).to_ascii_uppercase());
            i += 3;
        } else if bytes[i] < 0x80 {
            out.push(bytes[i] as char);
            i += 1;
        } else {
            // Multi-byte UTF-8 char: copy it verbatim via the original
            // &str slicing rather than byte-by-byte casting.
            let ch_len = utf8_char_len(bytes[i]);
            let end = (i + ch_len).min(bytes.len());
            out.push_str(std::str::from_utf8(&bytes[i..end]).unwrap_or(""));
            i = end;
        }
    }
    out
}

fn is_hex(b: u8) -> bool {
    b.is_ascii_hexdigit()
}

fn utf8_char_len(first_byte: u8) -> usize {
    if first_byte & 0x80 == 0 {
        1
    } else if first_byte & 0xE0 == 0xC0 {
        2
    } else if first_byte & 0xF0 == 0xE0 {
        3
    } else if first_byte & 0xF8 == 0xF0 {
        4
    } else {
        1
    }
}

/// Canonicalize `raw_url` per spec §7. Returns the canonical URL string.
pub fn canonicalize_url(raw_url: &str) -> Result<String, UrlError> {
    let parsed = parse_url(raw_url)?;

    let scheme_lower = parsed.scheme.to_lowercase();

    let normalized_path = normalize_percent_encoding(&normalize_url_path(parsed.path));
    let normalized_query = parsed.query.map(normalize_percent_encoding);

    let mut out = String::new();
    out.push_str(&scheme_lower);
    out.push(':');

    if let Some(authority) = parsed.authority {
        out.push_str("//");
        out.push_str(&canonicalize_authority(authority, &scheme_lower));
    }

    out.push_str(&normalized_path);

    if let Some(q) = normalized_query {
        if !q.is_empty() {
            out.push('?');
            out.push_str(&q);
        }
    }

    // fragment is always dropped -- never appended.

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c(s: &str) -> String {
        canonicalize_url(s).expect("should parse")
    }

    #[test]
    fn scheme_lowercased() {
        assert_eq!(c("HTTP://example.com/"), "http://example.com/");
        assert_eq!(c("HtTpS://example.com/"), "https://example.com/");
    }

    #[test]
    fn host_lowercased() {
        assert_eq!(c("http://EXAMPLE.com/"), "http://example.com/");
    }

    #[test]
    fn default_port_dropped() {
        assert_eq!(c("http://example.com:80/"), "http://example.com/");
        assert_eq!(c("https://example.com:443/"), "https://example.com/");
    }

    #[test]
    fn non_default_port_kept() {
        assert_eq!(c("http://example.com:8080/"), "http://example.com:8080/");
        assert_eq!(c("https://example.com:80/"), "https://example.com:80/");
    }

    #[test]
    fn userinfo_preserved_verbatim_not_case_folded() {
        assert_eq!(
            c("http://User:Pass@EXAMPLE.com/"),
            "http://User:Pass@example.com/"
        );
    }

    #[test]
    fn fragment_dropped() {
        assert_eq!(c("http://example.com/a#section"), "http://example.com/a");
        assert_eq!(c("http://example.com/#frag"), "http://example.com/");
    }

    #[test]
    fn query_preserved_and_omitted_if_empty() {
        assert_eq!(c("http://example.com/a?x=1"), "http://example.com/a?x=1");
        assert_eq!(c("http://example.com/a?"), "http://example.com/a");
    }

    #[test]
    fn percent_encoding_hex_uppercased_not_decoded() {
        assert_eq!(c("http://example.com/a%2fb"), "http://example.com/a%2Fb");
        // %2F must NOT become a literal '/'.
        assert!(!c("http://example.com/a%2fb").contains("a/b"));
    }

    #[test]
    fn percent_encoding_in_query_also_normalized() {
        assert_eq!(
            c("http://example.com/?q=a%2fb"),
            "http://example.com/?q=a%2Fb"
        );
    }

    #[test]
    fn literal_slash_never_becomes_percent_2f() {
        assert_eq!(c("http://example.com/a/b"), "http://example.com/a/b");
    }

    #[test]
    fn dot_segment_normalization_in_path() {
        assert_eq!(c("http://example.com/a/./b"), "http://example.com/a/b");
        assert_eq!(c("http://example.com/a/b/../c"), "http://example.com/a/c");
    }

    #[test]
    fn leading_dotdot_in_url_path_is_absorbed_by_the_empty_leading_segment() {
        // See QUESTIONS.md Q7: §7.1's algorithm pushes the EMPTY segment
        // produced by a leading '/' onto the stack (it has no special
        // empty-segment rule, unlike §6 step 5). So for "/../a", the
        // segments are ["", "..", "a"]: "" is pushed, then ".." pops it
        // (since stack-top "" is not literally ".."), then "a" is
        // pushed. Net effect: a SINGLE leading ".." is silently absorbed
        // by the synthetic empty segment, NOT preserved as "../a".
        assert_eq!(c("http://example.com/../a"), "http://example.com/a");
    }

    #[test]
    fn repeated_leading_dotdot_first_one_absorbed_rest_preserved() {
        // "/../../a" -> segments ["", "..", "..", "a"]: "" pushed, first
        // ".." pops it (stack empty), second ".." has nothing to pop
        // (stack empty) so it's pushed literally, then "a" pushed.
        // Result stack ["..", "a"] -> "../a", leading slash prepended.
        assert_eq!(c("http://example.com/../../a"), "http://example.com/../a");
    }

    #[test]
    fn dotdot_cancels_preceding_real_segment_then_next_dotdot_preserved() {
        // "/a/../../b": "" pushed; "a" pushed; ".." pops "a"; ".." has
        // top "" so it pops that too (stack empty); "b" pushed.
        // Result: "/b".
        assert_eq!(c("http://example.com/a/../../b"), "http://example.com/b");
    }

    #[test]
    fn relative_path_no_leading_slash_dotdot_not_absorbed() {
        // Without a leading '/', there is no synthetic empty first
        // segment to absorb a ".." -- so for a path with no leading
        // slash, leading/excess ".." segments ARE preserved literally,
        // matching the spec's stated "leading or repeated .. is
        // preserved" intent. This only fully holds when there's no
        // leading slash creating an absorbing empty segment first.
        // mailto:-style opaque paths (no authority) never start with
        // '/' in our test corpus, but a generic scheme + authority +
        // relative-looking path can still be constructed for this test
        // by using a path that doesn't begin with '/'. Per §7's overall
        // grammar this is unusual for an authority-having URL (paths
        // after an authority conventionally start with '/'), but
        // nothing in §7.1 forbids exercising the algorithm on such an
        // input directly.
        assert_eq!(super::normalize_url_path("a/../../b"), "../b");
        assert_eq!(super::normalize_url_path("../a"), "../a");
    }

    #[test]
    fn no_authority_omits_double_slash() {
        // mailto: has no "//" authority.
        assert_eq!(c("mailto:user@example.com"), "mailto:user@example.com");
    }

    #[test]
    fn opaque_scheme_path_preserved() {
        let result = c("mailto:User@Example.com");
        // mailto has no authority (no //), so the whole
        // "User@Example.com" is the *path*, not lowercased as a host.
        assert_eq!(result, "mailto:User@Example.com");
    }

    #[test]
    fn empty_path_with_authority_preserved_as_is() {
        // No trailing slash in input -> none added (canonicalization
        // does not invent a root path).
        assert_eq!(c("http://example.com"), "http://example.com");
    }

    #[test]
    fn ipv6_host_handled() {
        assert_eq!(c("http://[::1]:8080/a"), "http://[::1]:8080/a");
        // default port dropped even for IPv6 literal host
        assert_eq!(c("http://[::1]:80/a"), "http://[::1]/a");
    }

    #[test]
    fn non_http_scheme_has_no_default_port_so_any_port_kept() {
        assert_eq!(c("ftp://example.com:21/"), "ftp://example.com:21/");
    }

    #[test]
    fn missing_scheme_colon_is_error() {
        let result = canonicalize_url("example.com/a");
        assert!(result.is_err());
    }

    #[test]
    fn malformed_percent_sequence_passed_through_unchanged() {
        // Lone '%' at end of string, and '%' followed by non-hex chars:
        // left completely as-is, not uppercased, not erroring.
        assert_eq!(c("http://example.com/a%"), "http://example.com/a%");
        assert_eq!(c("http://example.com/a%zz"), "http://example.com/a%zz");
        assert_eq!(c("http://example.com/a%2"), "http://example.com/a%2");
    }

    #[test]
    fn malformed_non_numeric_port_kept_verbatim() {
        assert_eq!(c("http://example.com:abc/x"), "http://example.com:abc/x");
    }

    #[test]
    fn multiple_at_signs_in_authority_split_on_last() {
        // userinfo password containing a literal (non-percent-encoded)
        // '@' -- split on the LAST '@' so host/port parse correctly.
        assert_eq!(
            c("http://user:p@ss@EXAMPLE.com/"),
            "http://user:p@ss@example.com/"
        );
    }

    #[test]
    fn combination_full_url() {
        assert_eq!(
            c("HTTPS://User:Pw@EXAMPLE.COM:443/a/./b/../c%2fd?Q=1#frag"),
            "https://User:Pw@example.com/a/c%2Fd?Q=1"
        );
    }

    #[test]
    fn empty_but_present_authority_still_renders_double_slash() {
        // "file:///path" has an authority component that is the empty
        // string (present but empty), which is different from "no
        // authority component to render" (e.g. "mailto:x@y.com", which
        // never had "//" at all). Per §7's reassembly rule, "//" is
        // omitted "only when there is no authority component to
        // render" -- an empty-but-present authority still counts as
        // present, so "//" must still be emitted.
        assert_eq!(c("file:///path/to/x"), "file:///path/to/x");
    }
}
