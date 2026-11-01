"""Build both distributions twice and compare byte-for-byte hashes."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "SOURCE_DATE_EPOCH": "1767225600", "PYTHONHASHSEED": "0"}
    with tempfile.TemporaryDirectory() as temporary:
        outputs = []
        for index in range(2):
            destination = Path(temporary) / str(index)
            subprocess.run(
                [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(destination), str(root)],
                check=True,
                env=env,
            )
            outputs.append(
                {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in destination.iterdir()}
            )
        if outputs[0] != outputs[1]:
            raise SystemExit("Builds were not byte-identical")
        target = root / "dist"
        target.mkdir(exist_ok=True)
        for artifact in (Path(temporary) / "0").iterdir():
            shutil.copy2(artifact, target / artifact.name)
        (target / "checksums.json").write_text(json.dumps(outputs[0], indent=2) + "\n")
        print(json.dumps({"reproducible": True, "sha256": outputs[0]}, indent=2))


if __name__ == "__main__":
    main()
