"""Put the on-site triage flags (a Muse Glimmer hub proof record) next to a store, where the investigation run reads
them: python scripts/seed_triage.py <proof.json> <data dir>. Also writes the seconds-sent summary into the proof."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "src"))
from spoor.forensics.triage import FILE, from_proof, summary  # noqa: E402

proof_path, data_dir = Path(sys.argv[1]), Path(sys.argv[2])
proof = json.loads(proof_path.read_text(encoding="utf-8"))
tri = from_proof(proof)
s = summary(tri)
proof["sent"] = {k: s[k] for k in ("pad_s", "sent_s", "total_s", "sent_share", "cameras_flagged", "cameras", "windows")}
proof_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
(data_dir / FILE).write_text(json.dumps(tri, indent=1) + "\n", encoding="utf-8")
print(f"{s['sent_s']:.0f} s of {s['total_s']:.0f} s sent ({100 * s['sent_share']:.1f}%), "
      f"{s['cameras_flagged']}/{s['cameras']} cameras; wrote {data_dir / FILE}")
