"""Resolve an unchanged library seed to local MCP arguments (Python stdlib only)."""
from pathlib import Path
import argparse
import hashlib
import json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('name', choices=['two_straight', 'two_smooth', 'five_smooth'])
args = parser.parse_args()
root = Path(__file__).resolve().parent
manifest = json.loads((root / 'seed_manifest.json').read_text(encoding='utf-8'))
seed = next(s for s in manifest['seeds'] if s['name'] == args.name)
path = (root / seed['relative_path']).resolve()
assert root in path.parents and path.is_file(), 'Seed file is missing'
assert hashlib.sha256(path.read_bytes()).hexdigest() == seed['sha256'], 'Seed changed; recheck its native feature ID, count and mode'
print(json.dumps({'seed_file': str(path), 'seed_feature_id': seed['seed_feature_id'],
                  'interpolation': seed['interpolation'], 'required_section_count': seed['section_count']}, ensure_ascii=False, indent=2))
