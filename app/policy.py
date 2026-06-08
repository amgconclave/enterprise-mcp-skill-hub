from __future__ import annotations

from app.models import (
    DataSensitivity,
    PolicyInvocationContext,
    PolicySimulationRequest,
    PolicySimulationResult,
    SkillManifest,
)


class PolicyService:
    """Small local rule engine for enterprise skill invocation demos."""

    def simulate(
        self,
        skill: SkillManifest,
        request: PolicySimulationRequest | PolicyInvocationContext,
    ) -> PolicySimulationResult:
        reasons: list[str] = []
        matched_rules: list[str] = []
        decision = "allow"

        role = request.role
        environment = request.environment.lower()
        sensitivity = request.data_sensitivity
        action = request.requested_action.lower()

        self._match(matched_rules, reasons, "role-known", f"Role '{role}' is recognized.")
        self._match(
            matched_rules,
            reasons,
            "sensitivity-known",
            f"Data sensitivity '{sensitivity}' is recognized.",
        )

        if action != "invoke":
            decision = "deny"
            self._match(
                matched_rules,
                reasons,
                "action-invoke-only",
                "Local policy only allows skill invocation actions.",
            )

        if not skill.enabled or skill.status != "promoted":
            decision = "deny"
            self._match(
                matched_rules,
                reasons,
                "skill-must-be-promoted",
                "Skill must be promoted and enabled before governed invocation.",
            )

        if role in {"admin", "reviewer"}:
            self._match(
                matched_rules,
                reasons,
                "privileged-confidential-access",
                "Admin and reviewer roles may invoke confidential skills for review workflows.",
            )
        elif sensitivity == "confidential":
            decision = "deny"
            self._match(
                matched_rules,
                reasons,
                "confidential-requires-admin-or-reviewer",
                "Confidential data requires an admin or reviewer role.",
            )

        if role == "viewer" and action == "invoke" and sensitivity != "public":
            decision = "deny"
            self._match(
                matched_rules,
                reasons,
                "viewer-public-only",
                "Viewer role may only invoke skills with public data.",
            )

        if "agent-tools" in skill.tags and role == "viewer":
            decision = "deny"
            self._match(
                matched_rules,
                reasons,
                "viewer-no-agent-tools",
                "Viewer role cannot invoke agent-tool tagged skills.",
            )

        if environment in {"prod", "production"} and skill.provider != "mock" and role != "admin":
            decision = "deny"
            self._match(
                matched_rules,
                reasons,
                "production-external-provider-admin-only",
                "Production use of non-mock providers requires an admin role.",
            )

        if decision == "allow":
            self._match(
                matched_rules,
                reasons,
                "default-allow",
                "No denying policy rules matched.",
            )

        return PolicySimulationResult(
            skill_id=skill.id,
            role=role,
            environment=request.environment,
            data_sensitivity=sensitivity,
            requested_action=request.requested_action,
            decision=decision,
            reasons=reasons,
            matched_rules=matched_rules,
        )

    def access_summary(self, skill: SkillManifest, environment: str = "local") -> dict[str, list[DataSensitivity]]:
        summary: dict[str, list[DataSensitivity]] = {}
        for role in ("admin", "reviewer", "agent", "viewer"):
            allowed: list[DataSensitivity] = []
            for sensitivity in ("public", "internal", "confidential"):
                request = PolicySimulationRequest(
                    skill_id=skill.id,
                    role=role,
                    environment=environment,
                    data_sensitivity=sensitivity,
                    requested_action="invoke",
                )
                if self.simulate(skill, request).decision == "allow":
                    allowed.append(sensitivity)
            summary[role] = allowed
        return summary

    def risk_flags(self, skill: SkillManifest) -> list[str]:
        summary = self.access_summary(skill)
        flags: list[str] = []
        if "confidential" not in summary["agent"]:
            flags.append("policy_agent_confidential_restricted")
        if "confidential" not in summary["viewer"]:
            flags.append("policy_viewer_confidential_restricted")
        if summary["viewer"] == []:
            flags.append("policy_viewer_no_invoke_access")
        return flags

    def _match(self, matched_rules: list[str], reasons: list[str], rule: str, reason: str) -> None:
        matched_rules.append(rule)
        reasons.append(reason)
