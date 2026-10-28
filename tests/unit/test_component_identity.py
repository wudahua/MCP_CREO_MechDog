"""FEAT-023/008 T09A: component business-label identity projection (offline).

The join key is the model identity plus the native component feature_id.
Covered here: single-label mirroring, multi-label expression, unlabeled old
results, same label in different models, cross-job persistence, delete plus
reinsert (old references must not mispoint), stale/deleted identity
expression, generic-alias exclusion, no input mutation, compact/full query
consistency, controlled detail references and the 32 KiB page budget.
"""

import copy
import unittest

from creo_mechdog import component_identity
from creo_mechdog.model_queries import (
    RESPONSE_BUDGET,
    inspect_page,
    section_records,
    serialized_size,
)


def component(feature_id, name, transform=None):
    return {
        "feature_id": feature_id,
        "model_name": name,
        "transform": transform or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        "transform_source": "component_to_assembly",
        "packaged": False,
        "underconstrained": False,
        "constraints": [],
    }


def alias(source_model_id, source_revision, feature_id, op="assemble_component"):
    entry = {
        "feature_id": feature_id,
        "source_model_id": source_model_id,
        "source_revision": source_revision,
    }
    if op is not None:
        entry["op"] = op
    return entry


def model(model_id="a" * 32, components=None, aliases=None):
    return {
        "model_id": model_id,
        "model_name": "asm",
        "model_type": "assembly",
        "revision": 4,
        "status": "ready",
        "updated_at": "2026-10-28",
        "aliases": aliases if aliases is not None else {},
        "inspection": {
            "healthy": True,
            "has_solid": True,
            "model_type": "assembly",
            "components": components if components is not None else [],
            "counts": {"components": 1},
        },
    }


class ProjectionContract(unittest.TestCase):
    def test_single_label_mirrors_source_identity(self):
        source = model(
            components=[component(40, "c_job_0")],
            aliases={"plate_a": alias("m" * 32, 3, 40)},
        )
        (record,) = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )["components"]
        self.assertEqual(record["identity"], {"model_id": "a" * 32, "feature_id": 40})
        self.assertEqual(record["label"], "plate_a")
        self.assertEqual(record["labels"], ["plate_a"])
        self.assertEqual(record["label_state"], "single")
        self.assertEqual(record["source_model_id"], "m" * 32)
        self.assertEqual(record["source_revision"], 3)
        self.assertEqual(record["model_name"], "c_job_0")

    def test_multi_label_keeps_every_binding_and_no_singular_fields(self):
        source = model(
            components=[component(40, "c_job_0")],
            aliases={
                "plate_b": alias("m" * 32, 3, 40),
                "plate_a": alias("n" * 32, 1, 40),
            },
        )
        projection = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )
        (record,) = projection["components"]
        self.assertEqual(record["label_state"], "multi")
        self.assertIsNone(record["label"])
        self.assertIsNone(record["source_model_id"])
        self.assertIsNone(record["source_revision"])
        self.assertEqual(record["labels"], ["plate_a", "plate_b"])
        self.assertEqual(
            record["bindings"],
            [
                {"label": "plate_a", "source_model_id": "n" * 32, "source_revision": 1},
                {"label": "plate_b", "source_model_id": "m" * 32, "source_revision": 3},
            ],
        )

    def test_old_result_without_label_is_unlabeled_not_fabricated(self):
        source = model(
            components=[component(40, "C_A3C874E18A0445A1_0")],
            aliases={"base": {"feature_id": 1}},
        )
        (record,) = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )["components"]
        self.assertEqual(record["label_state"], "unlabeled")
        self.assertIsNone(record["label"])
        self.assertEqual(record["labels"], [])
        self.assertEqual(record["bindings"], [])
        self.assertIsNone(record["source_model_id"])
        self.assertIsNone(record["source_revision"])
        self.assertEqual(record["model_name"], "C_A3C874E18A0445A1_0")

    def test_same_label_in_different_models_never_cross_joins(self):
        aliases = {"plate_a": alias("m" * 32, 3, 40)}
        first = component_identity.project_component_identities(
            model(model_id="a" * 32, components=[component(40, "c_1_0")], aliases=aliases),
            [component(40, "c_1_0")],
        )
        second = component_identity.project_component_identities(
            model(model_id="b" * 32, components=[component(40, "c_2_0")], aliases=aliases),
            [component(40, "c_2_0")],
        )
        self.assertEqual(first["components"][0]["identity"]["model_id"], "a" * 32)
        self.assertEqual(second["components"][0]["identity"]["model_id"], "b" * 32)
        self.assertEqual(first["components"][0]["label"], "plate_a")
        self.assertEqual(second["components"][0]["label"], "plate_a")
        self.assertEqual(first["deleted_identities"], [])
        self.assertEqual(second["deleted_identities"], [])

    def test_binding_survives_a_later_unrelated_job(self):
        # Job 1 recorded the alias; job 2 only moved the component. The query
        # projection reads the persisted alias map, so the label still resolves.
        source = model(
            components=[component(40, "c_job1_0")],
            aliases={"plate_a": alias("m" * 32, 1, 40)},
        )
        source["inspection"]["components"][0]["transform"] = [
            [1, 0, 0, 10],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
        (record,) = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )["components"]
        self.assertEqual(record["label"], "plate_a")
        self.assertEqual(record["source_revision"], 1)

    def test_delete_then_reinsert_old_identity_never_mispoints(self):
        # plate_a was removed and reinserted: its binding now carries the NEW
        # feature_id 55. A stale binding still naming the deleted id 40 is a
        # deleted identity and must not merge onto the new record.
        source = model(
            components=[component(55, "c_job2_0")],
            aliases={
                "plate_a": alias("m" * 32, 2, 55),
                "legacy_ref": alias("m" * 32, 1, 40),
            },
        )
        projection = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )
        (record,) = projection["components"]
        self.assertEqual(record["identity"]["feature_id"], 55)
        self.assertEqual(record["labels"], ["plate_a"])
        self.assertNotIn("legacy_ref", record["labels"])
        (deleted,) = projection["deleted_identities"]
        self.assertEqual(deleted["identity"], {"model_id": "a" * 32, "feature_id": 40})
        self.assertEqual(deleted["labels"], ["legacy_ref"])
        self.assertEqual(deleted["reason"], "feature_id_not_in_verified_components")

    def test_generic_feature_aliases_are_never_components(self):
        source = model(
            components=[component(40, "c_job_0")],
            aliases={
                "base": {"feature_id": 1, "op": "sketch"},
                "pad": {"feature_id": 2, "op": "extrude"},
                "plate_a": alias("m" * 32, 3, 40),
            },
        )
        projection = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )
        self.assertEqual(projection["components"][0]["labels"], ["plate_a"])
        self.assertEqual(projection["deleted_identities"], [])

    def test_stale_op_stamped_binding_without_record_is_deleted_identity(self):
        source = model(
            components=[],
            aliases={"plate_a": alias("m" * 32, 3, 40)},
        )
        projection = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )
        self.assertEqual(projection["components"], [])
        (deleted,) = projection["deleted_identities"]
        self.assertEqual(deleted["labels"], ["plate_a"])

    def test_bad_source_values_are_not_mirrored(self):
        source = model(
            components=[component(40, "c_job_0")],
            aliases={
                "plate_a": {
                    "feature_id": 40,
                    "op": "assemble_component",
                    "source_model_id": 7,
                    "source_revision": "3",
                }
            },
        )
        (record,) = component_identity.project_component_identities(
            source, source["inspection"]["components"]
        )["components"]
        self.assertEqual(record["label"], "plate_a")
        self.assertIsNone(record["source_model_id"])
        self.assertIsNone(record["source_revision"])

    def test_projection_never_mutates_inputs(self):
        source = model(
            components=[component(40, "c_job_0")],
            aliases={"plate_a": alias("m" * 32, 3, 40)},
        )
        before = copy.deepcopy(source)
        component_identity.project_component_identities(source, source["inspection"]["components"])
        self.assertEqual(source, before)

    def test_identity_key_states_the_fixed_join(self):
        projection = component_identity.project_component_identities(model(), [], {})
        self.assertEqual(
            projection["identity_key"],
            {"model_id": "a" * 32, "key": "model_identity+feature_id"},
        )


class QuerySurfaceContract(unittest.TestCase):
    def test_compact_summary_does_not_expand_components(self):
        source = model(
            components=[component(40, "c_job_0")],
            aliases={"plate_a": alias("m" * 32, 3, 40)},
        )
        page = inspect_page(source)
        self.assertEqual(page["inspection"]["counts"]["components"], 1)
        self.assertNotIn("components", page["inspection"])
        self.assertLess(serialized_size(page), RESPONSE_BUDGET)

    def test_full_section_serves_identity_decorated_records(self):
        source = model(
            components=[component(40, "c_job_0")],
            aliases={"plate_a": alias("m" * 32, 3, 40)},
        )
        records = section_records(source, "components")
        self.assertEqual(records[0]["label"], "plate_a")
        self.assertEqual(records[0]["identity"], {"model_id": "a" * 32, "feature_id": 40})
        page = inspect_page(source, "full", "components")
        self.assertEqual(page["data"]["components"], records)

    def test_whole_and_paged_full_shapes_agree_on_labels(self):
        source = model(
            components=[component(40, "c_job_0"), component(41, "c_job_1")],
            aliases={
                "plate_a": alias("m" * 32, 3, 40),
                "plate_b": alias("m" * 32, 3, 41, op=None),
            },
        )
        whole = inspect_page(source, "full")
        self.assertNotIn("data", whole)
        paged = inspect_page(source, "full", "components", 50)
        self.assertEqual(whole["inspection"]["components"], paged["data"]["components"])
        self.assertEqual(whole["inspection"]["components"][1]["label"], "plate_b")

    def test_detail_reference_resolves_labels(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import bridge
        from creo_mechdog import inspection_refs

        source = model(
            components=[component(40, "c_job_0")],
            aliases={"plate_a": alias("m" * 32, 3, 40)},
        )
        with tempfile.TemporaryDirectory(prefix="t09a_ref_") as tmp:
            root = Path(tmp)
            with patch.object(bridge, "ROOT", root):
                split = dict(source)
                aliases = split.pop("aliases")
                split["aliases_ref"] = inspection_refs.make_ref(
                    aliases, root / "details", "aliases", prefix="detail"
                )
                records = section_records(split, "components")
        self.assertEqual(records[0]["label"], "plate_a")
        self.assertEqual(records[0]["source_model_id"], "m" * 32)

    def test_pages_with_many_bound_components_stay_in_budget(self):
        aliases = {f"plate_{index}": alias("m" * 32, index % 5, 100 + index) for index in range(40)}
        components = [
            component(
                100 + index,
                f"c_job_{index}",
                [[1, 0, 0, index], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
            )
            for index in range(40)
        ]
        source = model(components=components, aliases=aliases)
        cursor = None
        found = []
        while True:
            page = inspect_page(source, "full", "components", 200, cursor)
            self.assertLessEqual(serialized_size(page), RESPONSE_BUDGET)
            found.extend(page["data"]["components"])
            cursor = page["next_cursor"]
            if not cursor:
                self.assertTrue(page["complete"])
                break
        self.assertEqual(len(found), 40)
        self.assertEqual(found[0]["label"], "plate_0")
        self.assertEqual(found[39]["source_revision"], 39 % 5)


if __name__ == "__main__":
    unittest.main()
