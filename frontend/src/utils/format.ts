const labels: Record<string, string> = {
  REVIEW_REQUIRED: "Review required",
  PASS: "Passed policy",
  FAIL: "Failed policy",
  NOT_EVALUATED: "Not evaluated",
  ADVISORY_ONLY: "Advisory only",
  NOT_APPLICABLE: "Not applicable",
  INSUFFICIENT_DATA: "Insufficient data",
  APPLICABLE: "Applicable",
  MODELLED: "Model",
  IDENTIFIER: "Identifier",
  EXCLUDED: "Exclude",
  gaussian_copula: "Gaussian Copula",
  ctgan: "CTGAN",
  tvae: "TVAE",
  tstr_trtr_ratio: "Task-specific utility ratio",
  structural_validation: "Structural validation",
  holdout_column_shapes: "Holdout Column Shapes",
  holdout_column_pair_trends: "Holdout Column Pair Trends",
  exact_training_match_fraction: "Exact training match fraction",
  dcr_overfitting_protection: "DCR Overfitting Protection",
  dcr_baseline_protection: "DCR Baseline Protection",
  disclosure_protection: "Disclosure Protection",
};
export const human = (value: string) =>
  labels[value] ??
  value
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
export const number = (value: number | boolean | null | undefined) =>
  value == null || (typeof value === "number" && !Number.isFinite(value))
    ? "Unavailable"
    : typeof value === "boolean"
      ? value
        ? "Passed"
        : "Failed"
      : new Intl.NumberFormat("en", { maximumFractionDigits: 4 }).format(value);
export const date = (value: string | null | undefined) =>
  value
    ? new Date(value).toLocaleString("en-GB", {
        timeZone: "UTC",
        dateStyle: "medium",
        timeStyle: "short",
      }) + " UTC"
    : "Not recorded";
export const duration = (start: string | null, end: string | null) =>
  start
    ? `${Math.max(0, Math.round(((end ? new Date(end).getTime() : Date.now()) - new Date(start).getTime()) / 1000))} s${end ? "" : " elapsed"}`
    : "Not started";
