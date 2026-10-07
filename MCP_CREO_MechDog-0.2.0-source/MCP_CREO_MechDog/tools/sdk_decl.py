import json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
config=json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
inc=Path(config['creo_root'])/'Common Files/protoolkit/includes'
sources=[]
for path in inc.glob('*.h'):
    source=path.read_text(encoding='utf-8',errors='replace')
    source=re.sub(r'/\*.*?\*/','',source,flags=re.S)
    sources.append((path,re.findall(r'[^;{}\n]*(?:extern|typedef)[^;{}]*;',source,re.S)))
for name in sys.argv[1:]:
    found=False
    for path,declarations in sources:
        for declaration in declarations:
            if re.search(r'\b'+re.escape(name)+r'\b',declaration):
                print(path.name, ' '.join(declaration.split()))
                found=True
    if not found: print(name,'not found')
