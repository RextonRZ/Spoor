"""Content-addressed private storage. Originals are written once, hashed while copying, then made read-only."""

import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


class MediaStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        for sub in ("originals", "derivatives", "frame_tables", "manifests"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def original_path(self, sha: str) -> Path:
        return self.root / "originals" / sha[:2] / sha

    def derivative_path(self, sha: str, suffix: str) -> Path:
        return self.root / "derivatives" / sha[:2] / f"{sha}{suffix}"

    def put_original(self, src: Path) -> tuple[str, Path, bool]:
        """Copy `src` into the store. Returns (sha256, stored_path, already_existed). Never modifies `src`."""
        digest = hashlib.sha256()
        tmp_dir = self.root / "originals"
        with src.open("rb") as fin, tempfile.NamedTemporaryFile(dir=tmp_dir, delete=False) as fout:
            while chunk := fin.read(CHUNK):
                digest.update(chunk)
                fout.write(chunk)
            tmp = Path(fout.name)
        sha = digest.hexdigest()
        dest = self.original_path(sha)
        if dest.exists():
            tmp.unlink()
            return sha, dest, True
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dest)
        os.chmod(dest, stat.S_IREAD)
        return sha, dest, False

    def put_derivative(self, produced: Path, suffix: str) -> tuple[str, Path]:
        sha = sha256_file(produced)
        dest = self.derivative_path(sha, suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            produced.unlink()
        else:
            shutil.move(produced, dest)
            os.chmod(dest, stat.S_IREAD)
        return sha, dest

    def write_json(self, sub: str, name: str, data: dict) -> Path:
        path = self.root / sub / f"{name}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    def read_json(self, sub: str, name: str) -> dict:
        return json.loads((self.root / sub / f"{name}.json").read_text())

    def delete_file(self, path: Path) -> None:
        """Retention/deletion path (PRD §7.1): clear the read-only bit, then remove."""
        if path.exists():
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            path.unlink()
