from app.bootstrap import BUILTIN_MANIFESTS, create_state


def test_builtin_manifests_are_valid() -> None:
    state = create_state()

    results = [
        state.validator.validate_manifest(manifest.model_dump(mode="json"))
        for manifest in BUILTIN_MANIFESTS
    ]

    assert all(result.valid for result in results)
    assert len(state.registry.list()) == 6


def test_invalid_manifest_is_rejected() -> None:
    state = create_state()

    result = state.validator.validate_manifest(
        {
            "id": "bad id",
            "name": "Broken",
            "version": "1.0.0",
            "description": "Invalid manifest.",
            "input_schema": {"type": "array"},
            "output_schema": {"type": "object", "properties": {}},
        }
    )

    assert not result.valid
    assert result.errors


def test_registration_records_version_and_audit_event() -> None:
    state = create_state()
    manifest = BUILTIN_MANIFESTS[0].model_copy(update={"version": "1.0.1"})

    state.registry.register(manifest, actor="pytest")

    versions = state.registry.versions(manifest.id)
    assert versions[-1].version == "1.0.1"
    assert any(event.action == "skill.registered" for event in state.audit.events)
