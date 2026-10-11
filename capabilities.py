"""Release scope. Registered tools are not a claim that every Creo operation works."""
from __future__ import annotations
from version import VERSION

REGISTERED_OPERATIONS = (
    'airfoil_sketch', 'update_airfoil', 'update_sketch_geometry', 'feature_group',
    'reorder_features', 'axis_pattern', 'geometry_transform', 'set_geometry_transform',
    "sketch", "extrude", "revolve", "hole", "round", "chamfer", "datum_plane", "datum_axis",
    "shell", "dimension_pattern", "mirror", "sweep", "loft", "draft", "sheetmetal_wall",
    "sheetmetal_flange", "sheetmetal_unbend", "sheetmetal_flat_pattern", "sheetmetal_bend_back",
    "assemble_component", "component_placement", "component_constraints", "remove_component",
    "set_dimensions", "set_sketch_dimensions", "set_parameters", "set_relations", "feature_tree",
    "regenerate", "save", "export", "dump_tree",
    "udf_inspect", "udf_create", "datum_csys", "datum_points", "surface_fill", "thicken", "solidify", "boolean_bodies", "rib",
    "drawing_model", "drawing_sheet", "drawing_view", "drawing_projection", "drawing_view_update",
    "drawing_note", "drawing_note_update", "drawing_table", "drawing_table_cell", "drawing_dimension", "drawing_delete",
)

UNAVAILABLE_OPERATIONS = {
    "loft": "Direct Blend creation and insertion into existing parts remain unavailable. Use creo_new_loft_part with a saved seed matching the requested section count and interpolation.",
}

def require_available(operations: list[dict]) -> None:
    unavailable = [op['op'] for op in operations if op['op'] in UNAVAILABLE_OPERATIONS]
    if unavailable:
        details = '; '.join(f"{name}: {UNAVAILABLE_OPERATIONS[name]}" for name in dict.fromkeys(unavailable))
        raise ValueError(f"Not available in the {VERSION} release candidate; no native job was queued. {details}")

def families() -> dict:
    return {
        'seed_library': {'enabled': True, 'scope': 'MIT native seeds bundled with source; SHA256 validation, local registration and automatic count/mode selection',
                         'automatic_pairs': ['2/straight','2/smooth','5/smooth'],
                         'limits': 'no automatic download, arbitrary seed generation or mode/count conversion'},
        'airfoil': {'enabled': True, 'scope': 'symmetric NACA 00xx native sketch splines; chord/thickness/twist/origin/pivot edits preserve sketch and Blend IDs',
                    'native_test': 'five smooth stations, two sequential middle-section edits and edit after a native group axis pattern; STL section comparison',
                    'limits': 'no camber; metadata driven MCP edits, not Creo relation-driven airfoil dimensions; creation-time sample count is fixed'},
        'sketch_geometry_edit': {'enabled': True, 'scope': 'in-place line/polyline/rectangle/circle/spline replacement; entity names/types/counts retained',
                                'limits': 'replaces dimensions/constraints with automatic dimensions and clears named dimension/airfoil metadata'},
        'placement': {'enabled': True, 'scope': 'native body FlexMove or quilt/geometry Move, in-place translation/rotation edits, local feature groups, reorder and axis patterns',
                      'native_test': 'body rotate/translate/edit with true solid bounding boxes; quilt rotate/translate/thicken/edit; five-section blade group pattern and later airfoil edit; save/erase/reload',
                      'limits': 'body branch can require Flexible Modeling license; copy-original, multiple bodies, custom csys, complex quilts and datum/curve combinations require local validation'},
        'drawing': {'enabled': True, 'scope': 'native DRW sheets, general/projected views, driving dimensions, notes, tables, edits, deletion and PDF',
                    'limits': 'owned part/sheetmetal snapshots; no live source update, assembly drawings, sections, detail views, GD&T or automatic BOM'},
        'datums': {'enabled': True, 'scope': 'coordinate systems and dimensioned point arrays in addition to planes and axes',
                   'native_test': 'XYZ offsets 10/20/30, Z rotation 45 degrees, native origin check and offset dimension edit'},
        'surface_solid': {'enabled': True, 'scope': 'planar fill, thicken and solidify',
                          'native_test': '20 x 10 fill, symmetric thickness 2 to 3; plane cut of a cube',
                          'limits': 'closed-quilt solidification, curved-quilt offset/cut and all side options need further validation'},
        'boolean_bodies': {'enabled': True, 'native_test': 'overlapping cubes: union 1500, difference 500 and intersection 500 mm3',
                           'limits': 'multi-target/tool lists and keep_tools require further native validation'},
        'rib': {'enabled': True, 'scope': 'native profile rib driven by an open sketch',
                'limits': 'sketch must intersect the solid; material side depends on sketch direction; trajectory ribs are not wrapped'},
        'udf': {'enabled': True, 'scope': 'local UDF metadata and independent native feature-group placement with reference/variable-dimension mapping',
                'limits': 'part/sheetmetal only; exact reference prompts required; assembly UDFs, quadrants, variable parameters and manufacturing UDFs are not wrapped; libraries supplied by user'},
        'mirror': {'enabled': True, 'native_test': 'whole solid about a principal datum plane',
                   'limits': 'whole-part/geometry references only; feature/subtree mirror is rejected'},
        'sweep': {'enabled': True, 'native_test': 'straight trajectory, circular constant section, named diameter edit',
                  'limits': 'constant section; other trajectories, thin/cut/surface branches need installation-specific validation'},
        'draft': {'enabled': True, 'native_test': 'constant unsplit draft on a planar face with a planar neutral reference',
                  'limits': 'variable, split and rib draft are not high-level tools'},
        'loft': {'enabled': False, 'reason': UNAVAILABLE_OPERATIONS['loft'],
                 'alternative_tool': 'creo_new_loft_part'},
        'loft_seed': {'enabled': True, 'tool': 'creo_new_loft_part',
                      'scope': 'new native part by rebinding an automatically selected bundled seed or explicit compatible seed to new XY sketch/airfoil sections',
                      'section_count_input_range': [2, 20],
                      'seed_section_count_must_match': True,
                      'interpolation': ['straight', 'smooth'],
                      'tested_section_count_mode_pairs': [{'section_count': 2, 'interpolation': 'straight'},
                                                          {'section_count': 2, 'interpolation': 'smooth'},
                                                          {'section_count': 5, 'interpolation': 'smooth'}],
                      'mode_verification': 'requested interpolation must match the saved seed; native PRO_FEAT_INFO checked before save, after parameter edits and after reload',
                      'native_test': 'five-section smooth rectangles and NACA 0012 spline airfoils; middle sketch/plane edits; saved reload, all-section STL checks and failed-assertion rollback; two-section rectangle/circle/triangle regression',
                      'limits': 'requires a saved solid Blend seed with matching section count and interpolation, Chinese/English Creo; XY sketches with strictly increasing Z offsets; no seed section insertion/removal, mode conversion, existing-target insertion, cut/surface or tangency controls; seed endpoint settings and datums are inherited; input range is not proof that every count/profile is tested; free endpoints may produce identical geometry with two sections'},
        'sheetmetal': {'enabled': True, 'scope': 'first flat wall, attached flange, unbend, bend-back and flat pattern',
                      'native_test': '40 x 30 x 1 wall, 90 degree flange with R2/R3 bend, followed by unfolding and refolding',
                      'limits': 'first wall uses thin extrusion then native conversion; bend relief, forms, hems and jogs are not high-level tools'},
        'assembly': {'enabled': True,
                     'native_test': 'part snapshots, rigid placement, removal, 3 datum-plane align constraints and 20 mm offset',
                     'limits': 'MCP-owned part/sheetmetal sources; no nested assemblies; source edits do not update snapshots; mate/insert/csys/default placement need further validation'},
    }
