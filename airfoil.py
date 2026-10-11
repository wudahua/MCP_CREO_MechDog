"""Symmetric NACA 00xx sections; shapes are native sketch splines, not imports."""
from __future__ import annotations
import math
from schema import AirfoilProfile, SketchOp


def entities(profile: dict) -> list[dict]:
    profile = AirfoilProfile.model_validate(profile).model_dump()
    chord, thickness = profile['chord'], profile['thickness_ratio']
    angle = math.radians(profile['twist_deg'])
    ca, sa = math.cos(angle), math.sin(angle)
    ox, oy = profile['origin']
    def position(x, y):
        x = (x - profile['pivot_fraction']) * chord
        y *= chord
        return [ox + x * ca - y * sa, oy + x * sa + y * ca]
    raw = []
    for index in range(profile['points_per_side']):
        x = (1 - math.cos(math.pi * index / (profile['points_per_side'] - 1))) / 2
        y = 5 * thickness * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x*x + 0.2843 * x**3 - 0.1015 * x**4)
        raw.append((x, y))
    upper = [position(x, y) for x, y in raw]
    lower = [position(x, -y) for x, y in reversed(raw)]
    return [dict(type='spline', name='upper', points=upper),
            dict(type='line', name='trailing', start=upper[-1], end=lower[0]),
            dict(type='spline', name='lower', points=lower)]


def prepare(operations: list[dict], aliases: dict) -> list[dict]:
    aliases = {key: dict(value) for key, value in aliases.items()}
    result = []
    for source in operations:
        op = dict(source)
        if op['op'] == 'airfoil_sketch':
            op['entities'] = entities(op['profile'])
            op['dimensions'], op['constraints'] = [], []
            aliases[op['label']] = {'airfoil': op['profile']}
        elif op['op'] == 'update_airfoil':
            previous = aliases.get(op['sketch'], {}).get('airfoil')
            if not previous:
                raise ValueError('Sketch has no airfoil definition; create it with creo_create_airfoil_section or creo_new_airfoil_blade')
            op['profile'] = AirfoilProfile.model_validate({**previous, **op['values']}).model_dump()
            op['entities'] = entities(op['profile'])
            aliases[op['sketch']]['airfoil'] = op['profile']
        elif op['op'] == 'update_sketch_geometry':
            # The existing entity names/types are checked by the native editor.
            checked = SketchOp.model_validate({'op': 'sketch', 'label': 'geometry_check', 'entities': op['entities']})
            op['entities'] = [entry.model_dump() for entry in checked.entities]
            if op['sketch'] in aliases:
                aliases[op['sketch']].pop('airfoil', None)
        result.append(op)
    return result
