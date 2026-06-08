from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.models import JsonDict, SkillManifest, ValidationResult


TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


class SkillValidator:
    def validate_manifest(self, payload: JsonDict) -> ValidationResult:
        try:
            manifest = SkillManifest.model_validate(payload)
        except ValidationError as exc:
            return ValidationResult(valid=False, errors=[str(error["msg"]) for error in exc.errors()])

        errors = self._validate_schema(manifest.input_schema, "input_schema")
        errors.extend(self._validate_schema(manifest.output_schema, "output_schema"))
        return ValidationResult(valid=not errors, errors=errors, manifest_id=manifest.id)

    def validate_invocation(self, manifest: SkillManifest, payload: JsonDict) -> list[str]:
        return self._validate_payload(manifest.input_schema, payload)

    def _validate_schema(self, schema: JsonDict, label: str) -> list[str]:
        errors: list[str] = []
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            errors.append(f"{label}.properties must be an object.")
            return errors
        required = schema.get("required", [])
        if not isinstance(required, list):
            errors.append(f"{label}.required must be a list when present.")
        for field, definition in properties.items():
            if not isinstance(definition, dict):
                errors.append(f"{label}.{field} must be an object.")
                continue
            schema_type = definition.get("type")
            if schema_type not in TYPE_MAP:
                errors.append(f"{label}.{field} has unsupported type {schema_type!r}.")
        return errors

    def _validate_payload(self, schema: JsonDict, payload: JsonDict) -> list[str]:
        errors: list[str] = []
        properties: dict[str, Any] = schema.get("properties", {})
        required: list[str] = schema.get("required", [])
        for field in required:
            if field not in payload:
                errors.append(f"Missing required field: {field}")
        for field, value in payload.items():
            if field not in properties:
                continue
            expected = properties[field].get("type")
            expected_type = TYPE_MAP.get(expected)
            if expected_type and not isinstance(value, expected_type):
                errors.append(f"{field} must be {expected}.")
        return errors
