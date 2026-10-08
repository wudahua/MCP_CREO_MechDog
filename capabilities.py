"""Release scope. Registered tools are not a claim that every Creo operation works."""
from __future__ import annotations
from version import VERSION

REGISTERED_OPERATIONS = (
    "sketch", "extrude", "revolve", "hole", "round", "chamfer", "datum_plane", "datum_axis",
    "shell", "dimension_pattern", "mirror", "sweep", "loft", "draft", "sheetmetal_wall",
    "sheetmetal_flange", "sheetmetal_unbend", "sheetmetal_flat_pattern", "sheetmetal_bend_back",
    "assemble_component", "component_placement", "component_constraints", "remove_component",
    "set_dimensions", "set_sketch_dimensions", "set_parameters", "set_relations", "feature_tree",
    "regenerate", "save", "export", "dump_tree",
)

UNAVAILABLE_OPERATIONS = {
    "loft": "Native blend/loft creation has not passed Creo 10 regeneration and saved-file verification.",
}

def require_available(operations: list[dict]) -> None:
    unavailable = [op['op'] for op in operations if op['op'] in UNAVAILABLE_OPERATIONS]
    if unavailable:
        details = '; '.join(f"{name}: {UNAVAILABLE_OPERATIONS[name]}" for name in dict.fromkeys(unavailable))
        raise ValueError(f"Not available in the {VERSION} release candidate; no native job was queued. {details}")

def families() -> dict:
    return {
        'mirror': {'enabled': True, 'native_test': 'whole solid about a principal datum plane',
                   'limits': 'whole-part/geometry references only; feature/subtree mirror is rejected'},
        'sweep': {'enabled': True, 'native_test': 'straight trajectory, circular constant section, named diameter edit',
                  'limits': 'constant section; other trajectories, thin/cut/surface branches need installation-specific validation'},
        'draft': {'enabled': True, 'native_test': 'constant unsplit draft on a planar face with a planar neutral reference',
                  'limits': 'variable, split and rib draft are not high-level tools'},
        'loft': {'enabled': False, 'reason': UNAVAILABLE_OPERATIONS['loft']},
        'sheetmetal': {'enabled': True, 'scope': 'first flat wall, attached flange, unbend, bend-back and flat pattern',
                      'native_test': '40 x 30 x 1 wall, 90 degree flange with R2/R3 bend, followed by unfolding and refolding',
                      'limits': 'first wall uses thin extrusion then native conversion; bend relief, forms, hems and jogs are not high-level tools'},
        'assembly': {'enabled': True,
                     'native_test': 'part snapshots, rigid placement, removal, 3 datum-plane align constraints and 20 mm offset',
                     'limits': 'MCP-owned part/sheetmetal sources; no nested assemblies; source edits do not update snapshots; mate/insert/csys/default placement need further validation'},
    }
