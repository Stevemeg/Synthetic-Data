import type { Overrides, Profile } from "../components/TabularConfiguration";
import type { PolicyRule } from "../types/domain";
export function inferredOverrides(
  profile: Profile,
  saved?: Overrides,
): Overrides {
  return Object.fromEntries(
    profile.columns.map((c) => [
      c.name,
      {
        role: c.suggested_role,
        semantic_type:
          c.inferred_type === "unsupported" || c.suggested_role === "IDENTIFIER"
            ? "categorical"
            : c.inferred_type,
        annotations: [],
        ...(c.suggested_role === "IDENTIFIER"
          ? { identifier_strategy: "synthetic_sequence" }
          : {}),
        ...saved?.[c.name],
      },
    ]),
  );
}
export function requirement(rule: PolicyRule) {
  return [
    rule.equals != null ? `= ${rule.equals ? "Passed" : "Failed"}` : "",
    rule.minimum != null ? `≥ ${rule.minimum}` : "",
    rule.maximum != null ? `≤ ${rule.maximum}` : "",
    rule.required ? "Required" : "Optional",
  ]
    .filter(Boolean)
    .join(" · ");
}
