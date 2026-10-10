"""Emit public SDK enum names; values are resolved by the C++ compiler."""
from pathlib import Path
import json
import re

HEADERS = ['ProElemId.h', 'ProFeatType.h', 'ProExtrude.h', 'ProRevolve.h', 'ProDtmCrv.h',
           'ProDtmPln.h', 'ProDtmAxis.h', 'ProRound.h', 'ProChamfer.h', 'ProHole.h',
           'ProShell.h', 'ProPattern.h', 'ProSecdimType.h', 'ProSecconstr.h', 'ProMirror.h',
           'ProSweep.h', 'ProBodyOpts.h', 'ProFeature.h', 'ProFeatForm.h', 'ProDirection.h',
           'ProDraft.h', 'ProSmtFlangeWall.h', 'ProSmtFlatWall.h', 'ProRegularUnbend.h',
           'ProSmtBendBack.h', 'ProAsmcomp.h', 'ProSmtDrvSurf.h']


def generate(root: Path) -> int:
    config = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    inc = Path(config['creo_root']) / 'Common Files/protoolkit/includes'
    names = set()
    for header in HEADERS:
        source = (inc / header).read_text(encoding='utf-8', errors='replace')
        source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
        names.update(re.findall(r'^\s*#define\s+(PRO_(?:E|FEAT)_[A-Z0-9_]+)\s+(?:\d+|\([^\n]+\))', source, re.M))
        for block in re.findall(r'\benum\s*\w*\s*\{([^}]+)\}', source, re.S):
            names.update(re.findall(r'(?:^|,)\s*(PRO_[A-Z0-9_]+)\s*(?:=|,|$)', block, re.M))
    lines = ['// Enum names generated from the locally installed Creo 10 SDK.',
             *['#include <' + h + '>' for h in HEADERS],
             'static const std::map<std::string,int> tk_constants = {']
    lines += ['{"' + n + '",static_cast<int>(' + n + ')},' for n in sorted(names)]
    lines += ['};', '']
    out = root / 'native/constants.inc'
    value = '\n'.join(lines)
    if not out.exists() or out.read_text(encoding='utf-8') != value:
        out.write_text(value, encoding='utf-8')
    return len(names)


if __name__ == '__main__':
    print('SDK constant names:', generate(Path(__file__).resolve().parents[1]))
