"""DEV-051 T02 offline verdict tests for the FEAT-034 live driver.

``tools/test_arc_direction_live.py`` keeps its judgments pure so this module
can pin them without a Creo session. The two named regressions prove the fixed
judgment defects: a case fails when the native arc echo or the reload evidence
is missing even when the measured volume matches the oracle ("volume alone
never passes"), and the reload flag is evidence only inside ``result`` —
a flag at the terminal top level is not evidence and must not pass.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import test_arc_direction_live as driver

MISSING = object()

ALIASES = {"seg": {"feature_id": 11}, "body": {"feature_id": 22}}


def native_echo(direction: int = 1, sweep_deg: float = 90.0, name: str = "arc_a") -> dict:
    return {
        "name": name,
        "source": "native",
        "query_code": 0,
        "frame": "sketch_local",
        "start_uv": [10.0, 0.0],
        "end_uv": [0.0, 10.0],
        "start_tangent_uv": [0.0, 1.0],
        "end_tangent_uv": [-1.0, 0.0],
        "dir": direction,
        "sweep_deg": sweep_deg,
    }


def sketch_record(echo: dict | None = None) -> dict:
    record = {"op": "sketch", "index": 0, "label": "seg", "succeeded": True}
    if echo is not None:
        record["arc_geometry"] = [echo]
    return record


def update_record(preserved: int | None = None, echo: dict | None = None) -> dict:
    record = {
        "op": "update_sketch_geometry",
        "index": 0,
        "label": "",
        "sketch": "seg",
        "succeeded": True,
    }
    if preserved is not None:
        record["preserved_feature_id"] = preserved
    if echo is not None:
        record["arc_geometry"] = [echo]
    return record


def terminal(
    *,
    status: str = "succeeded",
    operations: list[dict] | None = None,
    reload_value: object = True,
    top_level_reload: object = MISSING,
    aliases: dict | None = None,
    revision: int = 1,
    extra_result: dict | None = None,
) -> dict:
    """A job terminal shaped like a real ``creo_get_job`` reply."""
    result: dict = {"success": status == "succeeded"}
    if operations is not None:
        result["operations"] = operations
    if reload_value is not MISSING:
        result["saved_file_reloaded_and_verified"] = reload_value
    if aliases is not None:
        result["aliases"] = aliases
    if extra_result:
        result.update(extra_result)
    out = {
        "job_id": "job-1",
        "model_id": "model-1",
        "status": status,
        "revision": revision,
        "result": result,
    }
    if top_level_reload is not MISSING:
        out["saved_file_reloaded_and_verified"] = top_level_reload
    return out


def inspection(volume: float | None) -> dict:
    return {"inspection": {"volume_mm3": volume}}


CREATE_CASE = {"case": "case_ok", "start": 0.0, "end": 90.0, "dir": -1}
EDIT_CASE = {"case": "edit_ok", "start": 0.0, "end": 90.0, "from_dir": 1, "to_dir": -1}
ILLEGAL_CASE = {"case": "bad_ok", "kind": "schema", "start": 0.0, "end": 90.0, "dir": 0}


class MissingEvidenceCannotPassTests(unittest.TestCase):
    """The two fixed judgment defects: volume alone never passes a case."""

    def test_missing_reload_evidence_cannot_pass(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        for label, reload_value in (
            ("absent", MISSING),
            ("null", None),
            ("false", False),
        ):
            with self.subTest(reload=label):
                terminal_dict = terminal(
                    operations=[sketch_record(native_echo(-1, 270.0))],
                    reload_value=reload_value,
                )
                row = driver.judge_create_case(CREATE_CASE, terminal_dict, inspection(volume))
                self.assertFalse(row["passed"])
                self.assertIn("reload_verification_missing", row["failures"])

    def test_missing_native_arc_echo_cannot_pass(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        for label, operations, expected in (
            ("absent", [sketch_record()], "native_arc_echo_missing"),
            ("unknown", [sketch_record(native_echo(-1, 270.0))], None),
            ("no_sweep", [sketch_record(native_echo(-1, 270.0))], None),
        ):
            with self.subTest(echo=label):
                if label == "unknown":
                    operations = [sketch_record({**native_echo(-1, 270.0), "source": "unknown"})]
                    expected = "native_arc_echo_not_measured"
                if label == "no_sweep":
                    echo = native_echo(-1, 270.0)
                    del echo["sweep_deg"]
                    operations = [sketch_record(echo)]
                    expected = "native_arc_echo_missing"
                terminal_dict = terminal(operations=operations)
                row = driver.judge_create_case(CREATE_CASE, terminal_dict, inspection(volume))
                self.assertFalse(row["passed"])
                self.assertIn(expected, row["failures"])

    def test_top_level_reload_flag_is_not_evidence(self):
        # The old driver read the flag at the terminal top level and found it
        # there even for jobs without any save evidence. That value must never
        # count as reload verification.
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        terminal_dict = terminal(
            operations=[sketch_record(native_echo(-1, 270.0))],
            reload_value=MISSING,
            top_level_reload=True,
        )
        self.assertIsNone(driver.reload_flag(terminal_dict))
        row = driver.judge_create_case(CREATE_CASE, terminal_dict, inspection(volume))
        self.assertFalse(row["passed"])
        self.assertIn("reload_verification_missing", row["failures"])

    def test_volume_only_evidence_cannot_pass(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        row = driver.judge_create_case(
            CREATE_CASE, terminal(reload_value=MISSING), inspection(volume)
        )
        self.assertFalse(row["passed"])
        self.assertIn("native_arc_echo_missing", row["failures"])
        self.assertIn("reload_verification_missing", row["failures"])

    def test_complete_create_evidence_passes(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        row = driver.judge_create_case(
            CREATE_CASE,
            terminal(operations=[sketch_record(native_echo(-1, 270.0))]),
            inspection(volume),
        )
        self.assertEqual(row["failures"], [])
        self.assertTrue(row["passed"])
        self.assertIs(row["saved_file_reloaded_and_verified"], True)

    def test_echo_with_wrong_direction_or_sweep_fails(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        for label, echo, expected in (
            ("dir", native_echo(1, 270.0), "arc_echo_dir_mismatch"),
            ("sweep", native_echo(-1, 90.0), "arc_echo_sweep_mismatch"),
        ):
            with self.subTest(mismatch=label):
                row = driver.judge_create_case(
                    CREATE_CASE, terminal(operations=[sketch_record(echo)]), inspection(volume)
                )
                self.assertFalse(row["passed"])
                self.assertIn(expected, row["failures"])


class DirectionEditTests(unittest.TestCase):
    """In-place direction switches: geometry must really change downstream."""

    @staticmethod
    def good_before():
        return terminal(
            operations=[sketch_record(native_echo(1, 90.0))], aliases=ALIASES, revision=1
        )

    @staticmethod
    def good_after():
        return terminal(
            operations=[update_record(11, native_echo(-1, 270.0))],
            aliases=ALIASES,
            revision=2,
        )

    def test_direction_edit_passes_with_full_evidence(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        row = driver.judge_direction_edit(
            EDIT_CASE, self.good_before(), self.good_after(), inspection(volume)
        )
        self.assertEqual(row["failures"], [])
        self.assertTrue(row["passed"])
        self.assertIs(row["identity"]["sketch_feature_id_preserved"], True)
        self.assertIs(row["identity"]["downstream_feature_id_preserved"], True)

    def test_direction_edit_requires_changed_geometry(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, 1)
        row = driver.judge_direction_edit(
            EDIT_CASE, self.good_before(), self.good_after(), inspection(volume)
        )
        self.assertFalse(row["passed"])
        self.assertIn("volume_mismatch", row["failures"])
        self.assertIn("geometry_did_not_change", row["failures"])

    def test_direction_edit_requires_revision_increment(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        after = self.good_after()
        after["revision"] = 1
        row = driver.judge_direction_edit(EDIT_CASE, self.good_before(), after, inspection(volume))
        self.assertFalse(row["passed"])
        self.assertIn("revision_not_incremented", row["failures"])

    def test_direction_edit_requires_reload_evidence(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        after = self.good_after()
        after["result"].pop("saved_file_reloaded_and_verified")
        row = driver.judge_direction_edit(EDIT_CASE, self.good_before(), after, inspection(volume))
        self.assertFalse(row["passed"])
        self.assertIn("reload_verification_missing", row["failures"])

    def test_direction_edit_identity_contradiction_fails(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        after = terminal(
            operations=[update_record(12, native_echo(-1, 270.0))],
            aliases={"seg": {"feature_id": 11}, "body": {"feature_id": 99}},
            revision=2,
        )
        row = driver.judge_direction_edit(EDIT_CASE, self.good_before(), after, inspection(volume))
        self.assertFalse(row["passed"])
        self.assertIn("sketch_identity_changed", row["failures"])
        self.assertIn("downstream_identity_changed", row["failures"])

    def test_missing_identity_data_is_recorded_but_not_judged(self):
        volume = driver.oracle_volume_mm3(0.0, 90.0, -1)
        before = terminal(operations=[sketch_record(native_echo(1, 90.0))], revision=1)
        after = terminal(operations=[update_record(None, native_echo(-1, 270.0))], revision=2)
        row = driver.judge_direction_edit(EDIT_CASE, before, after, inspection(volume))
        self.assertEqual(row["failures"], [])
        self.assertTrue(row["passed"])
        self.assertIsNone(row["identity"]["sketch_feature_id_preserved"])
        self.assertIsNone(row["identity"]["downstream_feature_id_preserved"])


class IllegalEditTests(unittest.TestCase):
    """Illegal edits must be rejected and must not touch geometry or revision."""

    @staticmethod
    def outcome(rejected=True, terminal_value=None, error_text="rejected"):
        return {
            "rejected": rejected,
            "error_text": error_text,
            "terminal": terminal_value,
            "job_id": None,
        }

    def test_accepted_illegal_edit_fails(self):
        row = driver.judge_illegal_edit(
            ILLEGAL_CASE, self.outcome(rejected=False, error_text=None), 5.0, 5.0, 2, 2
        )
        self.assertFalse(row["passed"])
        self.assertIn("illegal_edit_accepted", row["failures"])

    def test_changed_model_fails(self):
        row = driver.judge_illegal_edit(ILLEGAL_CASE, self.outcome(), 5.0, 6.0, 2, 2)
        self.assertFalse(row["passed"])
        self.assertIn("model_changed_after_illegal_edit", row["failures"])

    def test_changed_revision_fails(self):
        row = driver.judge_illegal_edit(ILLEGAL_CASE, self.outcome(), 5.0, 5.0, 2, 3)
        self.assertFalse(row["passed"])
        self.assertIn("revision_changed_after_illegal_edit", row["failures"])

    def test_missing_revision_evidence_fails(self):
        row = driver.judge_illegal_edit(ILLEGAL_CASE, self.outcome(), 5.0, 5.0, 2, None)
        self.assertFalse(row["passed"])
        self.assertIn("revision_evidence_missing", row["failures"])

    def test_unverified_rollback_fails(self):
        failed = terminal(status="failed", extra_result={"rollback_succeeded": False})
        row = driver.judge_illegal_edit(
            ILLEGAL_CASE, self.outcome(terminal_value=failed), 5.0, 5.0, 2, 2
        )
        self.assertFalse(row["passed"])
        self.assertIn("rollback_not_verified", row["failures"])

    def test_false_model_unchanged_fails(self):
        failed = terminal(
            status="failed",
            extra_result={"rollback_succeeded": True, "model_unchanged": False},
        )
        row = driver.judge_illegal_edit(
            ILLEGAL_CASE, self.outcome(terminal_value=failed), 5.0, 5.0, 2, 2
        )
        self.assertFalse(row["passed"])
        self.assertIn("model_changed_after_illegal_edit", row["failures"])

    def test_schema_rejection_with_untouched_model_passes(self):
        row = driver.judge_illegal_edit(ILLEGAL_CASE, self.outcome(), 5.0, 5.0, 2, 2)
        self.assertEqual(row["failures"], [])
        self.assertTrue(row["passed"])

    def test_native_rollback_evidence_passes(self):
        failed = terminal(
            status="failed",
            extra_result={"rollback_succeeded": True, "rollback_code": -8},
        )
        row = driver.judge_illegal_edit(
            ILLEGAL_CASE, self.outcome(terminal_value=failed), 5.0, 5.0, 2, 2
        )
        self.assertEqual(row["failures"], [])
        self.assertTrue(row["passed"])
        self.assertIs(row["rollback"]["rollback_succeeded"], True)


class SaveReloadTests(unittest.TestCase):
    def test_save_reload_passes_with_result_block_flag(self):
        volume = 142.69908169872414
        row = driver.judge_save_reload(
            "save_ok", terminal(reload_value=True), volume, inspection(volume)
        )
        self.assertEqual(row["failures"], [])
        self.assertTrue(row["passed"])

    def test_save_reload_missing_flag_fails(self):
        volume = 142.69908169872414
        for label, reload_value in (("absent", MISSING), ("null", None), ("false", False)):
            with self.subTest(reload=label):
                row = driver.judge_save_reload(
                    "save_bad",
                    terminal(reload_value=reload_value),
                    volume,
                    inspection(volume),
                )
                self.assertFalse(row["passed"])
                self.assertIn("reload_verification_missing", row["failures"])

    def test_save_reload_volume_mismatch_fails(self):
        row = driver.judge_save_reload(
            "save_bad", terminal(reload_value=True), 142.69908169872414, inspection(1.0)
        )
        self.assertFalse(row["passed"])
        self.assertIn("volume_mismatch", row["failures"])

    def test_save_reload_ignores_top_level_flag(self):
        volume = 142.69908169872414
        row = driver.judge_save_reload(
            "save_bad",
            terminal(reload_value=MISSING, top_level_reload=True),
            volume,
            inspection(volume),
        )
        self.assertFalse(row["passed"])
        self.assertIn("reload_verification_missing", row["failures"])


class LegacyGeometryPinningTests(unittest.TestCase):
    """The four accepted geometry cases stay byte-for-byte as accepted."""

    def test_four_geometry_cases_are_not_loosened(self):
        self.assertEqual(
            [case["case"] for case in driver.CASES],
            [
                "legacy_0_to_90",
                "legacy_90_to_0",
                "dir_minus1_90_to_0",
                "dir_minus1_0_to_90",
            ],
        )
        self.assertEqual(
            [(case["start"], case["end"], case["dir"]) for case in driver.CASES],
            [(0.0, 90.0, None), (90.0, 0.0, None), (90.0, 0.0, -1), (0.0, 90.0, -1)],
        )
        self.assertEqual(driver.TOLERANCE_MM3, 0.01)

    def test_oracle_volumes_keep_the_2026_10_29_values(self):
        volumes = [
            driver.oracle_volume_mm3(
                case["start"], case["end"], 1 if case["dir"] is None else case["dir"]
            )
            for case in driver.CASES
        ]
        for volume, accepted in zip(
            volumes,
            (
                142.69908169872414,
                1428.0972450961724,
                142.69908169872414,
                1428.0972450961724,
            ),
        ):
            self.assertAlmostEqual(volume, accepted, places=9)


class ReportPathTests(unittest.TestCase):
    def test_resolve_output_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "report.json"
            existing.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                driver.resolve_output(existing, "run")
            fresh = Path(tmp) / "fresh" / "report.json"
            self.assertEqual(driver.resolve_output(fresh, "run"), fresh)


class LiveCoverageInventoryTests(unittest.TestCase):
    """The live matrix must cover every aspect the T02 remainder asks for.

    The inventory is what the offline report publishes, so an aspect that
    loses its case would otherwise disappear silently from the evidence.
    """

    def test_every_required_aspect_names_at_least_one_live_case(self):
        inventory = driver.coverage_inventory()
        for aspect in (
            "direction_in_place_edit",
            "cross_zero",
            "tilted_frame",
            "downstream_regeneration",
            "illegal_edit",
            "save_reload",
            "create_geometry",
        ):
            with self.subTest(aspect=aspect):
                self.assertTrue(inventory[aspect], aspect)

    def test_the_named_cases_exist_in_the_live_tables(self):
        known = {
            case["case"]
            for case in [
                *driver.CASES,
                *driver.FRAME_CASES,
                *driver.EDIT_CASES,
                *driver.ILLEGAL_EDIT_CASES,
            ]
        }
        for aspect, names in driver.coverage_inventory().items():
            for name in names:
                with self.subTest(aspect=aspect, case=name):
                    self.assertIn(name, known)

    def test_cross_zero_and_tilted_frame_have_their_own_case(self):
        inventory = driver.coverage_inventory()
        self.assertIn("edit_switch_dir_cross_zero", inventory["cross_zero"])
        self.assertIn("edit_switch_dir_tilted_xz", inventory["tilted_frame"])

    def test_illegal_edits_cover_rejection_and_native_failure(self):
        kinds = {case["kind"] for case in driver.ILLEGAL_EDIT_CASES}
        self.assertEqual(kinds, {"schema", "native"})
        self.assertEqual(
            sorted(case["case"] for case in driver.ILLEGAL_EDIT_CASES),
            [
                "illegal_dir_float",
                "illegal_dir_zero",
                "illegal_full_circle",
                "illegal_open_profile",
                "illegal_zero_sweep",
            ],
        )


class OfflineReportTests(unittest.TestCase):
    """The offline stage must leave an auditable report on the given path."""

    def test_offline_writes_a_report_and_never_overwrites_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "run" / "report.json"
            code = driver.main(["--output", str(target)])
            self.assertEqual(code, 0)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "offline")
            self.assertEqual(report["native_acceptance"], "not_run")
            self.assertIn("coverage", report)
            self.assertTrue(report["provenance"]["source_fingerprint"])
            self.assertTrue(target.with_name("report.sha256").is_file())
            # A second run must refuse the existing report instead of
            # overwriting the history.
            self.assertEqual(driver.main(["--output", str(target)]), 2)

    def test_offline_never_creates_an_mcp_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            client = Mock(side_effect=AssertionError("MCP client must not be created"))
            with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                code = driver.main(["--output", str(target)])
            self.assertEqual(code, 0)
            client.assert_not_called()

    def test_a_single_live_flag_never_connects(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            client = Mock(side_effect=AssertionError("MCP client must not be created"))
            with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                code = driver.main(["--live", "--output", str(target)])
            self.assertEqual(code, 0)
            client.assert_not_called()
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["native_acceptance"], "not_run")


if __name__ == "__main__":
    unittest.main()
