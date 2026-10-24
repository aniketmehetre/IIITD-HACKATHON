"""Tests loading shared/api-schema.yaml and validating every JSON in shared/mocks/."""

import json
from pathlib import Path

import jsonschema
import yaml


def _resolve_schema(schema: dict, full_spec: dict) -> dict:
    """Recursively resolves $ref references within components/schemas for validation."""
    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema:
        ref_path = schema["$ref"]
        if ref_path.startswith("#/components/schemas/"):
            schema_name = ref_path.split("/")[-1]
            target = full_spec["components"]["schemas"][schema_name]
            return _resolve_schema(target, full_spec)

    resolved = {}
    for k, v in schema.items():
        if isinstance(v, dict):
            resolved[k] = _resolve_schema(v, full_spec)
        elif isinstance(v, list):
            resolved[k] = [
                _resolve_schema(item, full_spec) if isinstance(item, dict) else item for item in v
            ]
        else:
            resolved[k] = v
    return resolved


def test_shared_api_schema_valid_and_mocks_conform():
    """Verify shared/api-schema.yaml loads and all mock JSON files in shared/mocks validate."""
    # Find repository root from current test file
    test_dir = Path(__file__).resolve().parent
    repo_root = test_dir.parent.parent

    schema_file = repo_root / "shared" / "api-schema.yaml"
    mocks_dir = repo_root / "shared" / "mocks"

    assert schema_file.exists(), f"Schema file not found at {schema_file}"
    assert mocks_dir.exists(), f"Mocks directory not found at {mocks_dir}"

    with open(schema_file, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    assert spec.get("openapi") == "3.1.0"
    schemas = spec["components"]["schemas"]

    # Mapping of mock file to corresponding schema
    mock_mappings = {
        "health.json": spec["paths"]["/health"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"],
        "cases_post.json": schemas["CaseSummary"],
        "cases_list.json": spec["paths"]["/cases"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"],
        "case_detail.json": schemas["Case"],
        "case_events.json": spec["paths"]["/cases/{id}/events"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"],
        "case_result.json": schemas["Result"],
        "evidence_verify.json": spec["paths"]["/evidence/verify"]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"],
        "approve_report.json": spec["paths"]["/cases/{id}/approve-report"]["post"]["responses"][
            "200"
        ]["content"]["application/json"]["schema"],
        "graph_overview.json": schemas["GraphResponse"],
        "graph_payee.json": schemas["GraphResponse"],
        "metrics_summary.json": spec["paths"]["/metrics/summary"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"],
    }

    mock_files = list(mocks_dir.glob("*.json"))
    assert len(mock_files) >= 11, f"Expected at least 11 mock files, found {len(mock_files)}"

    for mock_file in mock_files:
        assert mock_file.name in mock_mappings, f"No schema mapped for mock file {mock_file.name}"
        with open(mock_file, "r", encoding="utf-8") as mf:
            mock_data = json.load(mf)

        raw_schema = mock_mappings[mock_file.name]
        resolved_schema = _resolve_schema(raw_schema, spec)

        # Validate with jsonschema Draft202012 / Draft7 validator
        validator_cls = jsonschema.validators.validator_for(resolved_schema)
        validator_cls.check_schema(resolved_schema)
        validator = validator_cls(resolved_schema)

        errors = list(validator.iter_errors(mock_data))
        assert not errors, (
            f"Mock file {mock_file.name} failed validation: {[e.message for e in errors]}"
        )
