from __future__ import annotations

from dataclasses import dataclass
import re


_LETTER = r"A-Za-zÁÉÍÓÚÝÐÞÆáéíóúýðþæÄÖäöÀÈÌÒÙàèìòù"
_KT_HYPHEN_RE = re.compile(r"(?<!\d)(\d{6})-(\d{4})(?!\d)")
_FOLD_TRANS = str.maketrans(
    {
        "á": "a",
        "à": "a",
        "ä": "a",
        "é": "e",
        "è": "e",
        "í": "i",
        "ì": "i",
        "ó": "o",
        "ò": "o",
        "ö": "o",
        "ú": "u",
        "ù": "u",
        "ý": "y",
        "ð": "d",
        "þ": "t",
        "æ": "a",
    }
)


@dataclass(frozen=True)
class PersonQuery:
    raw: str
    kennitala: str | None
    name: str | None
    name_tokens: tuple[str, ...]
    error: str | None = None

    @property
    def mode(self) -> str:
        if self.kennitala and self.name_tokens:
            return "name+kennitala"
        if self.kennitala:
            return "kennitala"
        return "name"


def _fold_is(s: str) -> str:
    return (s or "").translate(_FOLD_TRANS).lower()


def _kennitala_checksum_ok(digits: str) -> bool:
    if len(digits) != 10 or not digits.isdigit():
        return False
    d = [int(c) for c in digits]
    day = d[0] * 10 + d[1]
    month = d[2] * 10 + d[3]
    person_day = day if day <= 31 else day - 40
    if not (1 <= person_day <= 31 and 1 <= month <= 12):
        return False
    weights = [3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(w * x for w, x in zip(weights, d[:8]))
    rem = total % 11
    check = 0 if rem == 0 else 11 - rem
    if check == 10:
        return False
    return check == d[8]


def normalize_kennitala(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if not _kennitala_checksum_ok(digits):
        return None
    return f"{digits[:6]}-{digits[6:]}"


def parse_person_query(q: str) -> PersonQuery:
    raw = re.sub(r"\s+", " ", (q or "").strip())
    if not raw:
        return PersonQuery(
            raw=raw,
            kennitala=None,
            name=None,
            name_tokens=(),
            error="Enter a full name or kennitala.",
        )

    kennitala: str | None = None
    rest = raw
    compact = re.sub(r"[\s-]", "", raw)
    hyphen = _KT_HYPHEN_RE.search(raw)
    if hyphen:
        kt = normalize_kennitala(hyphen.group(0))
        if not kt:
            return PersonQuery(
                raw=raw,
                kennitala=None,
                name=None,
                name_tokens=(),
                error="Invalid kennitala (checksum or date).",
            )
        kennitala = kt
        rest = (raw[: hyphen.start()] + " " + raw[hyphen.end() :]).strip()
        rest = re.sub(r"\s+", " ", rest)
    elif re.fullmatch(r"\d{10}", compact):
        kt = normalize_kennitala(compact)
        if not kt:
            return PersonQuery(
                raw=raw,
                kennitala=None,
                name=None,
                name_tokens=(),
                error="Invalid kennitala (checksum or date).",
            )
        kennitala = kt
        rest = ""

    tokens = tuple(t for t in rest.split() if t)
    if tokens and len(tokens) < 2:
        return PersonQuery(
            raw=raw,
            kennitala=kennitala,
            name=rest or None,
            name_tokens=tokens,
            error="Use a full name (given name and surname) or a kennitala only.",
        )
    if tokens and any(len(t) < 2 for t in tokens):
        return PersonQuery(
            raw=raw,
            kennitala=kennitala,
            name=rest or None,
            name_tokens=tokens,
            error="Each name part must be at least two letters.",
        )
    if not kennitala and not tokens:
        return PersonQuery(
            raw=raw,
            kennitala=None,
            name=None,
            name_tokens=(),
            error="Enter a full name or kennitala.",
        )
    return PersonQuery(
        raw=raw,
        kennitala=kennitala,
        name=" ".join(tokens) if tokens else None,
        name_tokens=tokens,
    )


def inflected_name_tokens(token: str) -> list[str]:
    t = (token or "").strip().lower()
    if not t:
        return []
    out: list[str] = [t]
    if t.endswith("dóttir"):
        out.append(t[: -len("dóttir")] + "dóttur")
    elif t.endswith("dóttur"):
        out.append(t[: -len("dóttur")] + "dóttir")
    elif t.endswith("sonar"):
        out.append(t[:-2])
    elif t.endswith("son"):
        out.append(t + "ar")
    else:
        m = re.match(r"^(.+?)([áéíóúý])(n)(ar|u)?$", t)
        if m:
            stem, vowel, n, _suf = m.group(1), m.group(2), m.group(3), m.group(4)
            base = stem + vowel + n
            out.extend([base, base + "u", base + "ar"])
        elif t.endswith("ar") and len(t) > 3:
            out.append(t[:-2])
            out.append(t[:-2] + "u")
        elif t.endswith("u") and len(t) > 2 and t[-2] in "áéíóúýn":
            if t.endswith("nu"):
                base = t[:-1]
                out.extend([base, base + "ar"])
            else:
                out.append(t[:-1])
                out.append(t[:-1] + "ar")
        elif not t.endswith(("ar", "u")):
            out.append(t + "ar")
            out.append(t + "u")

    seen: set[str] = set()
    uniq: list[str] = []
    for v in out:
        if not v or v in seen:
            continue
        seen.add(v)
        uniq.append(v)
    return uniq


def _token_char_re(token: str) -> str:
    parts: list[str] = []
    for ch in token.lower():
        if ch in "aáàä":
            parts.append("[aáàä]")
        elif ch in "eéè":
            parts.append("[eéè]")
        elif ch in "iíì":
            parts.append("[iíì]")
        elif ch in "oóòö":
            parts.append("[oóòö]")
        elif ch in "uúù":
            parts.append("[uúù]")
        elif ch in "yý":
            parts.append("[yý]")
        elif ch in "dð":
            parts.append("[dð]")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def _name_token_re(token: str) -> str:
    variants = inflected_name_tokens(token)
    if len(variants) == 1:
        return _token_char_re(variants[0])
    return "(?:" + "|".join(_token_char_re(v) for v in variants) + ")"


def name_sql_regex(tokens: tuple[str, ...]) -> str:
    body = r"[[:space:]]+".join(_name_token_re(t) for t in tokens)
    return rf"(^|[^{_LETTER}]){body}($|[^{_LETTER}])"


def kennitala_sql_regex(kt: str) -> str:
    ddmm, rest = kt[:6], kt[7:]
    return rf"(^|[^0-9]){re.escape(ddmm)}-?{re.escape(rest)}($|[^0-9])"


def ilike_needles(tokens: tuple[str, ...]) -> list[str]:
    if not tokens:
        return []
    variants: set[str] = set()
    for v in inflected_name_tokens(tokens[0]):
        variants.add(v)
        folded = _fold_is(v)
        if folded:
            variants.add(folded)
    out: list[str] = []
    for v in sorted(variants):
        escaped = v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        out.append(f"%{escaped}%")
    return out


def name_py_regex(tokens: tuple[str, ...]) -> re.Pattern[str]:
    body = r"\s+".join(_name_token_re(t) for t in tokens)
    return re.compile(rf"(?<![{_LETTER}]){body}(?![{_LETTER}])", re.IGNORECASE)


def kennitala_py_regex(kt: str) -> re.Pattern[str]:
    ddmm, rest = kt[:6], kt[7:]
    return re.compile(rf"(?<!\d){re.escape(ddmm)}-?{re.escape(rest)}(?!\d)")


def highlight_preview(text: str, parsed: PersonQuery, window: int = 180) -> str:
    raw = text or ""
    patterns: list[re.Pattern[str]] = []
    if parsed.kennitala:
        patterns.append(kennitala_py_regex(parsed.kennitala))
    if parsed.name_tokens:
        patterns.append(name_py_regex(parsed.name_tokens))
    first: re.Match[str] | None = None
    for p in patterns:
        m = p.search(raw)
        if m:
            first = m
            break
    if not first:
        return raw[:400]
    start = max(0, first.start() - window)
    end = min(len(raw), first.end() + window)
    snippet = raw[start:end]
    offset = start

    def wrap(s: str, p: re.Pattern[str]) -> str:
        return p.sub(lambda m: "[[[" + m.group(0) + "]]]", s)

    for p in patterns:
        snippet = wrap(snippet, p)
    prefix = "…" if offset > 0 else ""
    suffix = "…" if end < len(raw) else ""
    return prefix + snippet + suffix
