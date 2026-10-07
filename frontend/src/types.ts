export type Modality = "tabular" | "timeseries" | "imaging" | "genomic";
export interface GenerationConfig {
  type: "timeseries" | "imaging";
  count: number;
  seed: number;
  modality?: string;
}
export interface Capability {
  maturity: "Stable" | "Beta" | "Experimental";
  available: boolean;
  reason: string;
  engines?: { name: string; maturity: string; version: string }[];
}
export interface Capabilities {
  capabilities: Record<Modality, Capability>;
  limits: {
    max_samples: number;
    max_images: number;
    max_upload_mb: number;
    tabular_max_generated_rows: number;
    ctgan_max_epochs: number;
    tvae_max_epochs: number;
  };
}
export interface GenerationResult {
  metadata: {
    run_id: string;
    modality: string;
    engine: string;
    requested_sample_count: number;
    produced_sample_count: number;
    seed: number;
    duration_seconds: number;
    source_schema_summary: Record<string, unknown>;
    warnings: string[];
    maturity: string;
  };
  artifacts: {
    location: string;
    media_type: string;
    role: string;
    download_url: string;
  }[];
}
export interface GeneratorProps {
  onGenerate: (config: GenerationConfig, file?: File) => Promise<void>;
  loading: boolean;
  capability?: Capability;
  maxCount: number;
  maxUploadMb: number;
}
