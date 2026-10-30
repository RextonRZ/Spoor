"""Fetch only the files we need out of the big Zenodo zips (HTTP Range: central directory, then each entry), so the
1.8 GB AndyData BVH zip and the 1.5 GB 100STYLE zip never have to be downloaded whole (Zenodo serves ~0.35 MB/s).

  py -X utf8 assets/mocap/fetch_sources.py list andydata [filter]
  py -X utf8 assets/mocap/fetch_sources.py get andydata <name-substring> [<name-substring> ...]

Writes into assets/mocap/raw/<source>/ (gitignored). Sources and licences: assets/mocap/sources.csv.
"""
import http.client
import struct
import sys
import time
import urllib.request
import zlib
from pathlib import Path

ZIPS = {
    "andydata": "https://zenodo.org/records/3254403/files/xsens_bvh.zip?download=1",  # CC BY 4.0, Maurice et al. 2019
    "andylabels": "https://zenodo.org/records/3254403/files/labels_csv.zip?download=1",
    "100style": "https://zenodo.org/records/8127870/files/100STYLE.zip?download=1",  # CC BY 4.0, Mason et al. 2022
}
RAW = Path(__file__).resolve().parent / "raw"


def _rng1(url, a, b):
    req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}", "User-Agent": "spoor-fetch"})
    with urllib.request.urlopen(req, timeout=120) as r:
        if r.status != 206:
            raise RuntimeError(f"no range support ({r.status})")
        total = int(r.headers["Content-Range"].split("/")[-1])
        return r.read(), total


def rng(url, a, b, chunk=4 << 20, tries=6):
    """Bytes a..b in 4 MB ranges, each retried (Zenodo drops long transfers: IncompleteRead)."""
    out, total = bytearray(), None
    for c0 in range(a, b + 1, chunk):
        for k in range(tries):
            try:
                part, total = _rng1(url, c0, min(b, c0 + chunk - 1))
                break
            except (OSError, http.client.HTTPException) as e:
                if k == tries - 1:
                    raise
                print(f"  retry {c0}: {e!r}", flush=True)
                time.sleep(2 + 3 * k)
        out += part
    return bytes(out), total


def central(url):
    tail, total = rng(url, 0, 0)
    tail, total = rng(url, max(0, total - 65536 - 22), total - 1)
    i = tail.rfind(b"PK\x05\x06")
    n, cd_size, cd_off = struct.unpack("<HII", tail[i + 10:i + 20])
    z64 = tail.rfind(b"PK\x06\x06")
    if cd_off == 0xFFFFFFFF and z64 >= 0:  # zip64
        n, cd_size, cd_off = struct.unpack("<QQQ", tail[z64 + 32:z64 + 56])
    cd, _ = rng(url, cd_off, cd_off + cd_size - 1)
    out, p = [], 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        meth, = struct.unpack("<H", cd[p + 10:p + 12])
        csize, usize = struct.unpack("<II", cd[p + 20:p + 28])
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off, = struct.unpack("<I", cd[p + 42:p + 46])
        name = cd[p + 46:p + 46 + nl].decode("utf-8", "replace")
        extra = cd[p + 46 + nl:p + 46 + nl + el]
        q = 0
        while q + 4 <= len(extra):  # zip64 extra field: the real sizes / offset
            hid, hl = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:
                vals, k = extra[q + 4:q + 4 + hl], 0
                if usize == 0xFFFFFFFF:
                    usize, = struct.unpack("<Q", vals[k:k + 8]); k += 8
                if csize == 0xFFFFFFFF:
                    csize, = struct.unpack("<Q", vals[k:k + 8]); k += 8
                if off == 0xFFFFFFFF:
                    off, = struct.unpack("<Q", vals[k:k + 8]); k += 8
            q += 4 + hl
        out.append(dict(name=name, method=meth, csize=csize, usize=usize, off=off))
        p += 46 + nl + el + cl
    return out


def get(url, e, dest):
    head, _ = rng(url, e["off"], e["off"] + 29)
    nl, el = struct.unpack("<HH", head[26:30])
    start = e["off"] + 30 + nl + el
    data, _ = rng(url, start, start + e["csize"] - 1)
    raw = zlib.decompress(data, -15) if e["method"] == 8 else data
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return len(raw)


if __name__ == "__main__":
    cmd, src = sys.argv[1], sys.argv[2]
    ents = central(ZIPS[src])
    if cmd == "list":
        flt = sys.argv[3] if len(sys.argv) > 3 else ""
        for e in ents:
            if flt in e["name"]:
                print(f"{e['usize'] / 1e6:9.2f} MB  {e['name']}")
        print(len(ents), "entries")
    else:
        want = sys.argv[3:]
        for e in ents:
            if e["name"].endswith("/") or not any(w in e["name"] for w in want):
                continue
            n = get(ZIPS[src], e, RAW / src / e["name"])
            print(f"got {e['name']} ({n / 1e6:.1f} MB)", flush=True)
