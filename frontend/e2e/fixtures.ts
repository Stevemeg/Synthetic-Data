const timestamp = "2026-10-05T08:00:00Z";
export const project = {
  id: "project-demo",
  name: "Cardio Readmission Research",
  description: "Demo · Programmatically generated fake data only.",
  status: "ACTIVE",
  created_at: timestamp,
  updated_at: timestamp,
  datasets: 1,
  runs: 1,
  evaluations: 1,
  reports: 1,
  latest_activity: timestamp,
  latest_decision: "REVIEW_REQUIRED",
};
export const profile = {
  dataset_id: "dataset-demo",
  compatible: true,
  row_count: 400,
  column_count: 5,
  warnings: ["Automatic inference is advisory. Review all roles."],
  columns: [
    {
      name: "patient_id",
      inferred_type: "categorical",
      suggested_role: "IDENTIFIER",
      null_percentage: 0,
      unique_count: 400,
      possible_free_text: false,
      all_null: false,
      warnings: ["Potential identifier: highly unique."],
    },
    {
      name: "age",
      inferred_type: "numerical",
      suggested_role: "MODELLED",
      null_percentage: 0,
      unique_count: 60,
      possible_free_text: false,
      all_null: false,
      warnings: [],
    },
    {
      name: "diagnosis_group",
      inferred_type: "categorical",
      suggested_role: "MODELLED",
      null_percentage: 0,
      unique_count: 3,
      possible_free_text: false,
      all_null: false,
      warnings: [],
    },
    {
      name: "readmitted",
      inferred_type: "boolean",
      suggested_role: "MODELLED",
      null_percentage: 0,
      unique_count: 2,
      possible_free_text: false,
      all_null: false,
      warnings: [],
    },
    {
      name: "clinical_notes",
      inferred_type: "categorical",
      suggested_role: "EXCLUDED",
      null_percentage: 0,
      unique_count: 400,
      possible_free_text: true,
      all_null: false,
      warnings: ["Potential free-text: excluded."],
    },
  ],
};
export const overrides = Object.fromEntries(
  profile.columns.map((c) => [
    c.name,
    {
      role: c.suggested_role,
      semantic_type:
        c.suggested_role === "IDENTIFIER" ? "categorical" : c.inferred_type,
      annotations:
        c.name === "age"
          ? ["QUASI_IDENTIFIER"]
          : c.name === "diagnosis_group"
            ? ["SENSITIVE_ATTRIBUTE"]
            : [],
      ...(c.suggested_role === "IDENTIFIER"
        ? { identifier_strategy: "synthetic_sequence" }
        : {}),
    },
  ]),
);
export const dataset = {
  id: "dataset-demo",
  project_id: project.id,
  name: "Synthetic Clinical Cohort · Demo synthetic source fixture",
  modality: "tabular",
  original_filename: "demo-synthetic-clinical-cohort.csv",
  row_count: 400,
  column_count: 5,
  size_bytes: 32000,
  sha256: "a".repeat(64),
  status: "READY",
  created_at: timestamp,
  metadata_json: { tabular_profile: profile, governance_overrides: overrides },
};
const applicable = (score: number) => ({
  score,
  applicability: "APPLICABLE",
  warnings: [],
});
export const structural = {
  passed: true,
  requested_rows: 400,
  produced_rows: 400,
  column_order_valid: true,
  identifier_collisions: [],
  excluded_columns_absent: true,
  rule_violations: [],
  missing_columns: [],
  unexpected_columns: [],
  nullability_violations: [],
  dtype_mismatches: [],
};
export const job = {
  id: "run-demo",
  project_id: project.id,
  dataset_id: dataset.id,
  modality: "tabular",
  engine: "gaussian_copula",
  status: "SUCCEEDED",
  requested_samples: 400,
  produced_samples: 400,
  random_seed: 42,
  created_at: timestamp,
  queued_at: timestamp,
  started_at: timestamp,
  finished_at: "2026-10-05T08:00:15Z",
  error_message: null,
  error_code: null,
  configuration_json: {
    columns: profile.columns.map((c) => ({
      name: c.name,
      ...overrides[c.name],
    })),
    split: {
      training_row_count: 320,
      holdout_row_count: 80,
      holdout_fraction: 0.2,
      split_seed: 42,
    },
  },
  metadata_json: {
    application_version: "0.5.0",
    application_commit: "c".repeat(40),
    warnings: [],
    tabular: {
      source_sha256: dataset.sha256,
      model_sha256: "b".repeat(64),
      synthetic_artifact: { sha256: "d".repeat(64) },
      engine_version: "1.25.0",
      structural_validation: structural,
      performance: {
        training_duration_seconds: 12,
        sampling_duration_seconds: 0.3,
      },
      split: { training_row_count: 320, holdout_row_count: 80 },
    },
  },
};
export const policy = {
  id: "policy-demo",
  project_id: project.id,
  name: "Illustrative Research Demo Policy",
  description: "Example thresholds only.",
  version: 1,
  policy_hash: "e".repeat(64),
  illustrative: true,
  created_at: timestamp,
  rules: {
    structural_validation: { equals: true, required: true },
    holdout_column_shapes: { minimum: 0.8, required: true },
    dcr_overfitting_protection: { minimum: 0.7, required: true },
  },
};
export const summary = {
  structural,
  quality: {
    training: {
      ...applicable(0.85),
      properties: {
        "Column Shapes": applicable(0.96),
        "Column Pair Trends": applicable(0.74),
      },
      column_metrics: [
        {
          Column: "age",
          Metric: "KSComplement",
          Score: 0.96,
          applicability: "APPLICABLE",
        },
        {
          Column: "diagnosis_group",
          Metric: "TVComplement",
          Score: 0.92,
          applicability: "APPLICABLE",
        },
      ],
      pair_metrics: [
        {
          "Column 1": "age",
          "Column 2": "readmitted",
          Metric: "ContingencySimilarity",
          Score: 0.74,
          applicability: "APPLICABLE",
        },
      ],
    },
    holdout: {
      ...applicable(0.81),
      properties: {
        "Column Shapes": applicable(0.91),
        "Column Pair Trends": applicable(0.71),
      },
      column_metrics: [
        {
          Column: "age",
          Metric: "KSComplement",
          Score: 0.9,
          applicability: "APPLICABLE",
        },
        {
          Column: "diagnosis_group",
          Metric: "TVComplement",
          Score: 0.78,
          applicability: "APPLICABLE",
        },
      ],
      pair_metrics: [
        {
          "Column 1": "age",
          "Column 2": "readmitted",
          Metric: "ContingencySimilarity",
          Score: 0.71,
          applicability: "APPLICABLE",
        },
      ],
    },
  },
  privacy: {
    exact_training: {
      exact_matching_generated_rows: 0,
      exact_match_fraction: 0,
    },
    dcr_baseline_protection: {
      ...applicable(0.62),
      breakdown: {
        median_DCR_to_real_data: {
          synthetic_data: 0.077,
          random_data_baseline: 0.124,
        },
      },
    },
    dcr_overfitting_protection: {
      score: 0.375,
      applicability: "ADVISORY_ONLY",
      warnings: [
        "Original train/holdout size ratio is outside the operational gating range.",
      ],
      methodology: { train_validation_ratio: 4, gating_eligible: false },
      breakdown: {
        synthetic_data_percentages: {
          closer_to_training: 0.8125,
          closer_to_holdout: 0.1875,
        },
      },
    },
    disclosure_protection: {
      ...applicable(1),
      breakdown: { cap_protection: 0.671, baseline_protection: 0.667 },
      configuration: {
        known_columns: ["age"],
        sensitive_columns: ["diagnosis_group"],
        computation_method: "cap",
      },
      real_partition: "HOLDOUT",
    },
  },
  utility: {
    ...applicable(0.92),
    task: "BINARY_CLASSIFICATION",
    target: "readmitted",
    trtr: {
      f1: 0.94,
      accuracy: 0.93,
      precision: 0.93,
      recall: 0.95,
      roc_auc: 0.96,
    },
    tstr: {
      f1: 0.86,
      accuracy: 0.85,
      precision: 0.81,
      recall: 0.92,
      roc_auc: 0.95,
    },
    comparisons: {
      f1: {
        absolute_delta: -0.08,
        ratio: 0.915,
        ratio_semantics: "TSTR/TRTR F1 ratio",
      },
      accuracy: {
        absolute_delta: -0.08,
        ratio: 0.914,
        ratio_semantics: "TSTR/TRTR accuracy ratio",
      },
    },
  },
  release: {
    decision: "REVIEW_REQUIRED",
    policy,
    reasons: ["DCR overfitting evidence is advisory."],
    meaning: "Configured policy only.",
    rules: [
      {
        metric: "structural_validation",
        actual_value: true,
        metric_applicability: "APPLICABLE",
        threshold: { equals: true, required: true },
        required: true,
        status: "PASS",
        reason: "Configured threshold satisfied",
      },
      {
        metric: "holdout_column_shapes",
        actual_value: 0.91,
        metric_applicability: "APPLICABLE",
        threshold: { minimum: 0.8, required: true },
        required: true,
        status: "PASS",
        reason: "Configured threshold satisfied",
      },
      {
        metric: "dcr_overfitting_protection",
        actual_value: 0.375,
        metric_applicability: "ADVISORY_ONLY",
        threshold: { minimum: 0.7, required: true },
        required: true,
        status: "INSUFFICIENT_DATA",
        reason: "Evidence is not eligible for release gating",
      },
    ],
  },
  warnings: [],
  duration_seconds: 8,
  generation_performance: {
    training_duration_seconds: 12,
    sampling_duration_seconds: 0.3,
  },
};
export const evaluation = {
  id: "evaluation-demo",
  project_id: project.id,
  dataset_id: dataset.id,
  generation_job_id: job.id,
  status: "SUCCEEDED",
  profile: "FULL",
  created_at: timestamp,
  started_at: timestamp,
  finished_at: "2026-10-05T08:00:23Z",
  error_message: null,
  result_summary_json: summary,
  configuration_json: {
    generation_engine: "gaussian_copula",
    request: { profile: "FULL", group_key: "patient_id" },
  },
};
export const artifact = {
  id: "artifact-report",
  job_id: "evaluation-job",
  artifact_type: "GOVERNANCE_REPORT",
  filename: "medsynth-guard_demo_governance-report.html",
  content_type: "text/html",
  size_bytes: 1000,
  sha256: "f".repeat(64),
  created_at: timestamp,
  downloadable: true,
  metadata_json: { evaluation_run_id: evaluation.id },
};
export const activity = [
  {
    id: "event-1",
    entity_id: evaluation.id,
    entity_type: "evaluation",
    event_type: "EVALUATION_SUCCEEDED",
    actor: "worker",
    created_at: timestamp,
  },
  {
    id: "event-2",
    entity_id: dataset.id,
    entity_type: "dataset",
    event_type: "DATASET_REGISTERED",
    actor: "anonymous",
    created_at: timestamp,
  },
];
export const caps = {
  capabilities: {
    tabular: {
      available: true,
      maturity: "Stable",
      reason: "Real fitted models",
      engines: [
        { name: "gaussian_copula" },
        { name: "ctgan" },
        { name: "tvae" },
      ],
    },
    timeseries: { available: true, maturity: "Beta" },
    imaging: { available: false, maturity: "Experimental" },
    genomic: { available: false, maturity: "Experimental" },
  },
  limits: {
    tabular_max_generated_rows: 10000,
    max_samples: 1000,
    max_upload_mb: 10,
    ctgan_max_epochs: 50,
    tvae_max_epochs: 50,
    max_images: 64,
  },
};
export const pageOf = <T>(items: T[]) => ({
  items,
  total: items.length,
  limit: 20,
  offset: 0,
});
