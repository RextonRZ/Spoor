"""Agents' own wording, shown in plain words (owner 2 Nov: "plain area names and local times, not BLIND_NW / UTC").

Only the display changes: ids the agents copy from the data (a site-plan area id, `zone_Z11`, `cam_CAM_19`) become the
names staff use, UTC times become the hub's local time, and a place said twice ("Exception Store (BLIND_NW)") is said
once. The meaning is not touched: the raw wording is kept next to it. Names come from the site and its plan (data), so
nothing here knows any particular site. A zone that shares its name with a plan area inside it (a room in its zone) is
called "<name> zone", so "outside the room, in its zone" keeps its meaning."""

import re
from datetime import datetime, timedelta, tzinfo

from spoor.contracts import Site, SitePlan

PH = "⟦{}⟧"  # a placeholder while places are merged


def place_name(name: str) -> str:
    """'Z11 Exception store' -> 'Exception store (Z11)'; a name that already reads well is kept."""
    m = re.match(r"^(Z\d+)\s+(.+)$", name)
    return f"{m.group(2)} ({m.group(1)})" if m else name


def _core(label: str) -> str:
    return re.sub(r"\s*\((Z\d+)\)$", "", label).removesuffix(" zone").lower()


def _places(site: Site, plan: SitePlan | None) -> list[tuple[str, list[str]]]:
    """(display label, every way the agents may write it), longest forms first."""
    out: dict[str, set[str]] = {}
    areas = {place_name(a.name): a for a in (plan.areas if plan else [])}
    for a in areas.values():
        label = place_name(a.name)
        out.setdefault(label, set()).update({a.area_id, a.name, label})
    for z in site.zones:
        m = re.match(r"^(Z\d+)\s+(.+)$", z.name)
        code, core = (m.group(1), m.group(2)) if m else (z.zone_id, z.name)
        label = f"{core} zone ({code})" if place_name(z.name) in areas else place_name(z.name)
        short = core.split(" and ")[0].split(" (")[0]
        forms = {z.zone_id, z.name, label, code, f"zone_{code}", f"{core} {code}", f"{short} {code}", f"{code} {short}"}
        if place_name(z.name) not in areas:
            forms |= {place_name(z.name), short}
        out.setdefault(label, set()).update(forms)
    return [(label, sorted({f for f in forms if f and len(f) > 1}, key=len, reverse=True)) for label, forms in out.items()]


ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")
UTC_CLOCK = re.compile(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\s?UTC|[+-]00:00)(?![\w:])")
OFFSET_CLOCK_RE = r"\b(\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}:\d{2})(?![\w:])"
RECORD_ID_RE = r"\s*\b(?:trk|obs|scan|media|finding|hypothesis|est)_[0-9a-f]{8,}\b"
OFFSET_CLOCK = re.compile(OFFSET_CLOCK_RE)
RECORD_ID = re.compile(RECORD_ID_RE)
BARE = re.compile(r"(?<![\d:.T])\d{2}:\d{2}:\d{2}(?:\.\d+)?(?![\d:])")


def _local_times(text: str, tz: tzinfo, hours: set[int]) -> str:
    def iso(m: re.Match) -> str:
        return datetime.fromisoformat(m.group(0)).astimezone(tz).strftime("%H:%M:%S")

    def utc(m: re.Match) -> str:
        hms = re.match(r"\d{2}:\d{2}:\d{2}", m.group(0)).group(0)
        t = datetime.fromisoformat(f"2000-01-01T{hms}+00:00")
        return t.astimezone(tz).strftime("%H:%M:%S")

    def bare(m: re.Match) -> str:
        # a bare clock is local unless it only makes sense as UTC (its hour is not one of the case's local hours, but
        # converted it is): agents copy UTC times without the Z
        hms = m.group(0)[:8]
        h = int(hms[:2])
        off = tz.utcoffset(None) or timedelta(0)
        as_local_from_utc = (h + int(off.total_seconds() // 3600)) % 24
        if hours and h not in hours and as_local_from_utc in hours:
            return utc(m)
        return hms

    def offset(m: re.Match) -> str:  # "14:32:32+08:00": a clock with its own offset
        t = datetime.fromisoformat(f"2000-01-01T{m.group(1)}{m.group(2)}")
        return t.astimezone(tz).strftime("%H:%M:%S")

    text = OFFSET_CLOCK.sub(offset, UTC_CLOCK.sub(utc, ISO.sub(iso, text)))
    return BARE.sub(bare, text)


def plain_words(text: str, site: Site, plan: SitePlan | None, tz: tzinfo, hours: set[int] | None = None) -> str:
    """`hours`: the local hours the case's records fall in (for telling a bare UTC clock from a local one)."""
    out = _local_times(RECORD_ID.sub("", text), tz, hours or set())  # record ids mean nothing to staff
    out = re.sub(r"\bcam_CAM_(\d+)\b", r"CAM \1", out)
    places = _places(site, plan)
    for i, (_label, forms) in enumerate(places):
        alt = "|".join(re.escape(f) for f in forms)
        out = re.sub(rf"(?i)(?<![\w-])(?:{alt})(?![\w-])", PH.format(i), out)
    cores = [_core(label) for label, _ in places]
    tok = re.compile("⟦(\\d+)⟧")

    def same(a: str, b: str) -> bool:
        return cores[int(a)] == cores[int(b)]

    for _ in range(3):  # "X (X)", "X X", "zone X": the same place said once (the first, more specific, name wins)
        out = re.sub("⟦(\\d+)⟧\\s*\\(\\s*⟦(\\d+)⟧\\s*\\)",
                     lambda m: m.group(0) if not same(m.group(1), m.group(2)) else PH.format(m.group(1)), out)
        out = re.sub("⟦(\\d+)⟧[\\s,/]+⟦(\\d+)⟧",
                     lambda m: m.group(0) if not same(m.group(1), m.group(2)) else PH.format(m.group(1)), out)
        out = re.sub("(?i)\\bzone\\s+(⟦\\d+⟧)", r"\1", out)
        for i, (label, _forms) in enumerate(places):  # "<zone id> Cage staging": the name again after the id
            short = re.escape(re.sub(r"\s*\(.*$", "", label).removesuffix(" zone").split(" and ")[0])
            out = re.sub(rf"(?i){re.escape(PH.format(i))}\s+{short}(?![\w-])", PH.format(i), out)
    out = tok.sub(lambda m: places[int(m.group(1))][0], out)
    for label, _forms in places:  # "Exception store (Exception store (Z11))": the bare name around its own label
        core = re.escape(re.sub(r"\s*\((Z\d+)\)$", "", label).removesuffix(" zone"))
        out = re.sub(rf"(?i)\b{core}\s*\(\s*{re.escape(label)}\s*\)", label, out)
    return re.sub(r"\s{2,}", " ", out).strip()
