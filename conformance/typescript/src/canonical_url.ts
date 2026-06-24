/**
 * ExternalResource URL Canonicalization (NIC v1.1 Freeze Commit D):
 * scheme/host lowercased, default ports removed, path dot-segments
 * normalized. Percent-encoding is NEVER decoded or re-encoded — only
 * hex-digit casing is normalized. %2F never becomes "/".
 *
 * Deliberately NOT built on the WHATWG URL class: it auto-decodes
 * percent-encoding in ways that would violate that rule.
 */
const DEFAULT_PORTS: Record<string, number> = { http: 80, https: 443 };

const USES_NETLOC = new Set([
  "",
  "ftp",
  "http",
  "gopher",
  "nntp",
  "telnet",
  "imap",
  "wais",
  "file",
  "mms",
  "https",
  "shttp",
  "snews",
  "prospero",
  "rtsp",
  "rtspu",
  "rsync",
  "svn",
  "svn+ssh",
  "sftp",
  "nfs",
  "git",
  "git+ssh",
  "ws",
  "wss",
]);

interface SplitUrl {
  scheme: string;
  netloc: string;
  path: string;
  query: string;
  fragment: string;
}

function urlsplit(raw: string): SplitUrl {
  let scheme = "";
  let rest = raw;
  const schemeMatch = /^([a-zA-Z][a-zA-Z0-9+.-]*):([\s\S]*)$/.exec(raw);
  if (schemeMatch) {
    scheme = schemeMatch[1];
    rest = schemeMatch[2];
  }

  let netloc = "";
  if (rest.startsWith("//")) {
    rest = rest.slice(2);
    const idx = rest.search(/[/?#]/);
    if (idx === -1) {
      netloc = rest;
      rest = "";
    } else {
      netloc = rest.slice(0, idx);
      rest = rest.slice(idx);
    }
  }

  let fragment = "";
  const hashIdx = rest.indexOf("#");
  if (hashIdx !== -1) {
    fragment = rest.slice(hashIdx + 1);
    rest = rest.slice(0, hashIdx);
  }

  let query = "";
  const qIdx = rest.indexOf("?");
  if (qIdx !== -1) {
    query = rest.slice(qIdx + 1);
    rest = rest.slice(0, qIdx);
  }

  return { scheme, netloc, path: rest, query, fragment };
}

interface Authority {
  username: string;
  password: string | null;
  hostname: string;
  port: number | null;
}

function parseAuthority(netloc: string): Authority {
  let userinfo = "";
  let hostport = netloc;
  const atIdx = netloc.lastIndexOf("@");
  if (atIdx !== -1) {
    userinfo = netloc.slice(0, atIdx);
    hostport = netloc.slice(atIdx + 1);
  }

  let username = "";
  let password: string | null = null;
  if (userinfo) {
    const colonIdx = userinfo.indexOf(":");
    if (colonIdx !== -1) {
      username = userinfo.slice(0, colonIdx);
      password = userinfo.slice(colonIdx + 1);
    } else {
      username = userinfo;
    }
  }

  let hostname = hostport;
  let port: number | null = null;
  const colonIdx = hostport.lastIndexOf(":");
  if (colonIdx !== -1) {
    const maybePort = hostport.slice(colonIdx + 1);
    if (/^\d+$/.test(maybePort)) {
      port = parseInt(maybePort, 10);
      hostname = hostport.slice(0, colonIdx);
    }
  }

  return { username, password, hostname, port };
}

function urlunsplit(
  scheme: string,
  netloc: string,
  url: string,
  query: string,
  fragment: string
): string {
  if (netloc || (scheme && USES_NETLOC.has(scheme) && url.slice(0, 2) !== "//")) {
    if (url && url[0] !== "/") url = "/" + url;
    url = "//" + (netloc || "") + url;
  }
  if (scheme) url = scheme + ":" + url;
  if (query) url = url + "?" + query;
  if (fragment) url = url + "#" + fragment;
  return url;
}

function normalizeUrlDotSegments(path: string): string {
  if (!path) return path;
  const leadingSlash = path.startsWith("/");
  const collapsed: string[] = [];
  for (const seg of path.split("/")) {
    if (seg === ".") {
      continue;
    } else if (seg === "..") {
      if (collapsed.length > 0 && collapsed[collapsed.length - 1] !== "..") {
        collapsed.pop();
      } else {
        collapsed.push(seg);
      }
    } else {
      collapsed.push(seg);
    }
  }
  let result = collapsed.join("/");
  if (leadingSlash && !result.startsWith("/")) {
    result = "/" + result;
  }
  return result;
}

const PCT_RE = /%([0-9A-Fa-f]{2})/g;

function upperCasePercentEncoding(s: string): string {
  return s.replace(PCT_RE, (_m, hex: string) => "%" + hex.toUpperCase());
}

export function canonicalizeUrl(rawUrl: string): string {
  const parts = urlsplit(rawUrl);
  const scheme = parts.scheme.toLowerCase();
  const auth = parseAuthority(parts.netloc);
  const hostname = auth.hostname.toLowerCase();

  let port = auth.port;
  if (port !== null && DEFAULT_PORTS[scheme] === port) {
    port = null;
  }

  let userinfo = "";
  if (auth.username) {
    userinfo = auth.username;
    if (auth.password) userinfo += ":" + auth.password;
    userinfo += "@";
  }

  let netloc = userinfo + hostname;
  if (port !== null) netloc += ":" + port;

  let path = normalizeUrlDotSegments(parts.path);
  path = upperCasePercentEncoding(path);
  const query = upperCasePercentEncoding(parts.query);

  return urlunsplit(scheme, netloc, path, query, "");
}
