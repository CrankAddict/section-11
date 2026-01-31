import json
from pathlib import Path

ARCHIVE_DIR = Path("archive")
INDEX_FILE = ARCHIVE_DIR / "index.json"

snapshots = sorted(
    [p.name for p in ARCHIVE_DIR.glob("*.json") if p.name != "index.json"]
)

index = {
    "snapshots": snapshots
}

with INDEX_FILE.open("w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

print(f"index.json updated with {len(snapshots)} snapshots")
