"""Historical content-addressed objects retain their byte identity after checkout."""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_checkpoint_evidence_objects_match_their_sha256_names():
    objects=ROOT/'docs/final-beige/predecessor/objects'
    files=sorted(objects.iterdir())
    assert files
    for path in files:
        assert len(path.name)==64
        assert hashlib.sha256(path.read_bytes()).hexdigest()==path.name,path.name
