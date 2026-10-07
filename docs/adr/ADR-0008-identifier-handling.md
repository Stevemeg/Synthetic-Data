# ADR-0008: Synthetic identifiers and excluded free text

Accepted in Phase 3. Separate role and semantic annotations. Infer possible
identifiers advisory-only; exclude original identifier values from fitting and
generate visibly synthetic, non-null, unique SYN sequences per output. Support
no real identifier formatting, government-number generation or Faker identities.
Exclude possible clinical free text; reject modelling it even through an override.
Persist role overrides/annotations for audit and later evaluation without claiming
privacy protection. Identifier uniqueness is structural, not a privacy guarantee.
