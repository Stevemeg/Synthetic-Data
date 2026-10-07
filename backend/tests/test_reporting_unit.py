"""Report wording and rule rendering preserve the persisted policy semantics."""

from backend.app.services.evaluation.reporting import rule_requirement


def test_nullable_policy_rule_fields_do_not_fabricate_requirements():
    assert (
        rule_requirement({"equals": None, "minimum": 0.8, "maximum": None, "required": True})
        == ">= 0.8; Required"
    )
    assert (
        rule_requirement({"equals": True, "minimum": None, "maximum": None, "required": True})
        == "= Passed; Required"
    )
    assert (
        rule_requirement({"equals": None, "minimum": None, "maximum": 0.01, "required": False})
        == "<= 0.01; Optional"
    )
