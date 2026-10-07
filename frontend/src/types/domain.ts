import type { Profile, Overrides } from "../components/TabularConfiguration";
export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};
export type Project = {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
  datasets?: number;
  runs?: number;
  evaluations?: number;
  reports?: number;
  latest_decision?: string | null;
  latest_activity?: string;
};
export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  modality: string;
  original_filename: string;
  row_count: number;
  column_count: number;
  size_bytes: number;
  sha256: string;
  status: string;
  created_at: string;
  metadata_json: {
    tabular_profile?: Profile;
    governance_overrides?: Overrides;
    columns?: string[];
  };
};
export type Column = {
  name: string;
  role: string;
  semantic_type: string;
  annotations: string[];
};
export type Structural = {
  passed: boolean;
  requested_rows?: number;
  produced_rows?: number;
  column_order_valid?: boolean;
  excluded_columns_absent?: boolean;
  identifier_collisions?: { column: string; count: number }[];
  rule_violations?: { column: string; rule: string; count: number }[];
  missing_columns?: string[];
  unexpected_columns?: string[];
  dtype_mismatches?: string[];
  nullability_violations?: { column: string; count: number }[];
};
export type Performance = {
  training_duration_seconds?: number;
  sampling_duration_seconds?: number;
  total_duration_seconds?: number;
};
export type Job = {
  id: string;
  project_id: string;
  dataset_id: string | null;
  modality: string;
  engine: string;
  status: string;
  requested_samples: number;
  produced_samples: number;
  random_seed: number;
  created_at: string;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
  configuration_json: {
    columns?: Column[];
    split?: Record<string, unknown>;
    tabular?: Record<string, unknown>;
    validation_rules?: Record<string, unknown>;
  };
  metadata_json: {
    warnings?: string[];
    duration_seconds?: number;
    application_version?: string;
    application_commit?: string;
    source_dataset_sha256?: string;
    engine_version?: string;
    tabular?: {
      structural_validation: Structural;
      performance: Performance;
      split: Record<string, unknown>;
      model_sha256?: string;
      source_sha256?: string;
      engine_version?: string;
      synthetic_artifact?: { sha256: string };
    };
    structural_validation?: Structural;
  };
};
export type Artifact = {
  id: string;
  job_id: string;
  filename: string;
  artifact_type: string;
  size_bytes: number;
  sha256: string;
  content_type: string;
  created_at: string;
  downloadable: boolean;
  metadata_json: { evaluation_run_id?: string };
};
export type Metric = {
  score: number | boolean | null;
  applicability: string;
  warnings?: string[];
  breakdown?: Record<string, number | null | Record<string, number>>;
  methodology?: {
    gating_eligible: boolean;
    train_validation_ratio: number | null;
  };
  configuration?: {
    known_columns: string[];
    sensitive_columns: string[];
    computation_method?: string;
  };
  real_partition?: string;
};
export type ColumnMetric = {
  Column: string;
  Metric: string;
  Score: number | null;
  applicability: string;
};
export type PairMetric = {
  "Column 1": string;
  "Column 2": string;
  Metric: string;
  Score: number | null;
  applicability: string;
};
export type Quality = Metric & {
  properties?: Record<string, Metric>;
  column_metrics?: ColumnMetric[];
  pair_metrics?: PairMetric[];
};
export type PolicyRule = {
  required: boolean;
  minimum?: number | null;
  maximum?: number | null;
  equals?: boolean | null;
  when?: string;
};
export type Policy = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  version: number;
  policy_hash: string;
  illustrative: boolean;
  created_at: string;
  rules: Record<string, PolicyRule>;
  usage?: number;
};
export type Release = {
  decision: string;
  meaning: string;
  policy?: Policy | null;
  reasons: string[];
  rules: {
    metric: string;
    actual_value: number | boolean | null;
    status: string;
    reason: string;
    metric_applicability: string;
    threshold: PolicyRule;
    required: boolean;
  }[];
};
export type Utility = Metric & {
  target?: string;
  task?: string;
  trtr?: Record<string, number | null>;
  tstr?: Record<string, number | null>;
  comparisons?: Record<
    string,
    {
      absolute_delta: number | null;
      ratio: number | null;
      ratio_semantics: string;
    }
  >;
};
export type Summary = {
  structural: Structural;
  quality: { training: Quality; holdout: Quality };
  privacy: {
    exact_training: {
      exact_matching_generated_rows: number;
      exact_match_fraction: number;
    };
    dcr_baseline_protection: Metric;
    dcr_overfitting_protection: Metric;
    disclosure_protection: Metric;
  };
  utility: Utility;
  release: Release;
  warnings: string[];
  duration_seconds: number;
  generation_performance?: Performance;
};
export type Evaluation = {
  id: string;
  project_id: string;
  dataset_id: string;
  generation_job_id: string;
  status: string;
  profile: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  result_summary_json: Partial<Summary>;
  configuration_json: {
    generation_engine?: string;
    request?: Record<string, unknown>;
  };
};
export type Activity = {
  user_id?: string | null;
  organization_id?: string | null;
  request_id?: string | null;
  id: string;
  event_type: string;
  actor: string;
  created_at: string;
  entity_id: string;
  entity_type: string;
};
export type Comparison = {
  rows: { evaluation_id: string; engine: string; results: Summary }[];
};
