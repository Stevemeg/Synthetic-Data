import { useRef, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from "@mui/material";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Dataset, Job } from "../../types/domain";
import type { Capabilities } from "../../types";
import {
  Facts,
  PageTitle,
  Section,
  State,
  Status,
} from "../../components/Workspace";
import TabularConfiguration, {
  type Overrides,
  type Profile,
} from "../../components/TabularConfiguration";
import { inferredOverrides } from "../../utils/governance";
import { human } from "../../utils/format";
const descriptions: Record<string, string> = {
  gaussian_copula:
    "Fast statistical baseline. Suitable for rapid experimentation and platform validation.",
  ctgan:
    "Neural synthesizer designed for mixed tabular data. Training typically takes longer.",
  tvae: "Variational autoencoder-based tabular synthesizer. Training typically takes longer.",
};
export default function Generation() {
  const { datasetId } = useParams();
  const navigate = useNavigate();
  const resource = useResource<Dataset>(`/api/v1/datasets/${datasetId}`);
  const caps = useResource<Capabilities>("/api/v1/capabilities");
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<Profile>();
  const [overrides, setOverrides] = useState<Overrides>();
  const [engine, setEngine] = useState("gaussian_copula");
  const [rows, setRows] = useState(400);
  const [seed, setSeed] = useState(42);
  const [holdout, setHoldout] = useState(0.2);
  const [splitSeed, setSplitSeed] = useState(42);
  const [epochs, setEpochs] = useState(10);
  const [batch, setBatch] = useState(100);
  const [ruleColumn, setRuleColumn] = useState("");
  const [nonNull, setNonNull] = useState(false);
  const [minimum, setMinimum] = useState("");
  const [maximum, setMaximum] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submission = useRef<{ signature: string; key: string } | null>(null);
  const d = resource.data;
  const analysis = profile ?? d?.metadata_json.tabular_profile;
  const values =
    overrides ??
    (analysis
      ? inferredOverrides(analysis, d?.metadata_json.governance_overrides)
      : {});
  const isTabular = d?.modality === "tabular";
  const max = isTabular
    ? (caps.data?.limits.tabular_max_generated_rows ?? 10000)
    : (caps.data?.limits.max_samples ?? 1000);
  const epochMax =
    engine === "ctgan"
      ? (caps.data?.limits.ctgan_max_epochs ?? 50)
      : (caps.data?.limits.tvae_max_epochs ?? 50);
  const valid =
    Number.isInteger(rows) &&
    rows >= 1 &&
    rows <= max &&
    Number.isInteger(seed) &&
    seed >= 0 &&
    seed <= 4294967295 &&
    (!isTabular ||
      (holdout >= 0 &&
        holdout <= 0.5 &&
        Number.isInteger(splitSeed) &&
        splitSeed >= 0 &&
        splitSeed <= 4294967295 &&
        (engine === "gaussian_copula" ||
          (Number.isInteger(epochs) &&
            epochs >= 1 &&
            epochs <= epochMax &&
            batch >= 10 &&
            batch <= 500 &&
            batch % 10 === 0)) &&
        (!minimum || Number.isFinite(Number(minimum))) &&
        (!maximum || Number.isFinite(Number(maximum))) &&
        (!minimum || !maximum || Number(minimum) <= Number(maximum))));
  const ready = isTabular
    ? !!analysis?.compatible &&
      Object.values(values).some((v) => v.role === "MODELLED")
    : true;
  async function preflight() {
    setBusy(true);
    setError("");
    try {
      const r = await api.post<Profile>(
        `/api/v1/datasets/${datasetId}/tabular/preflight`,
      );
      setProfile(r.data);
      setOverrides(
        inferredOverrides(r.data, d?.metadata_json.governance_overrides),
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    if (!d) return;
    setBusy(true);
    setError("");
    try {
      const body = {
        modality: d.modality,
        dataset_id: d.id,
        requested_samples: rows,
        random_seed: seed,
        ...(isTabular
          ? {
              engine,
              configuration: {
                holdout_fraction: holdout,
                split_seed: splitSeed,
                ...(engine === "gaussian_copula"
                  ? {}
                  : { epochs, batch_size: batch }),
              },
              metadata_overrides: values,
              validation_rules: ruleColumn
                ? {
                    [ruleColumn]: {
                      non_null: nonNull,
                      ...(minimum ? { numeric_min: Number(minimum) } : {}),
                      ...(maximum ? { numeric_max: Number(maximum) } : {}),
                    },
                  }
                : {},
            }
          : {}),
      };
      const signature = JSON.stringify(body);
      if (submission.current?.signature !== signature)
        submission.current = { signature, key: crypto.randomUUID() };
      const r = await api.post<Job>(
        `/api/v1/projects/${d.project_id}/jobs`,
        body,
        { headers: { "Idempotency-Key": submission.current.key } },
      );
      navigate(`/runs/${r.data.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        title="Create synthetic run"
        description="Review dataset governance and bounded configuration before intentional submission."
      />
      <State {...resource} />
      <State {...caps} />
      {error && <Alert severity="error">{error}</Alert>}
      {d && (
        <>
          <Link to={`/datasets/${d.id}`}>{d.name}</Link>
          <Stepper activeStep={step} alternativeLabel>
            {[
              "Dataset",
              "Columns",
              "Engine",
              "Configuration",
              "Review",
              "Submit",
            ].map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
          <Section
            title={
              [
                "Dataset context",
                "Column governance",
                "Select engine",
                "Run configuration",
                "Review run",
                "Submit run",
              ][step]
            }
          >
            {step === 0 && (
              <Facts
                values={{
                  Dataset: d.name,
                  Modality: human(d.modality),
                  "Source rows": d.row_count,
                  Project: (
                    <Link to={`/projects/${d.project_id}`}>Open project</Link>
                  ),
                }}
              />
            )}
            {step === 1 &&
              (isTabular ? (
                <Stack gap={2}>
                  <Button disabled={busy} onClick={() => void preflight()}>
                    Run preflight
                  </Button>
                  {analysis && (
                    <TabularConfiguration
                      profile={analysis}
                      overrides={values}
                      onChange={setOverrides}
                    />
                  )}
                </Stack>
              ) : (
                <Alert severity="info">
                  ECG signal extraction ignores the source label. Generated
                  windows are normalized and unlabeled.
                </Alert>
              ))}
            {step === 2 &&
              (isTabular ? (
                <Stack gap={2}>
                  <TextField
                    select
                    label="Engine"
                    value={engine}
                    onChange={(e) => setEngine(e.target.value)}
                  >
                    {["gaussian_copula", "ctgan", "tvae"].map((v) => (
                      <MenuItem
                        key={v}
                        value={v}
                        disabled={
                          !caps.data?.capabilities.tabular.engines?.some(
                            (e) => e.name === v,
                          )
                        }
                      >
                        {human(v)} ·{" "}
                        {v === "gaussian_copula" ? "Stable" : "Beta"}
                      </MenuItem>
                    ))}
                  </TextField>
                  <Status
                    value={engine === "gaussian_copula" ? "Stable" : "Beta"}
                  />
                  <Typography>{descriptions[engine]}</Typography>
                </Stack>
              ) : (
                <Stack gap={2}>
                  <Typography>ECG VAE</Typography>
                  <Status value="Beta" />
                  <Typography>
                    Train on extracted heartbeat windows. Privacy and diagnostic
                    validity are not established.
                  </Typography>
                </Stack>
              ))}
            {step === 3 && (
              <Stack gap={3}>
                <Typography variant="h6">Basic</Typography>
                <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
                  <TextField
                    label="Rows to generate"
                    type="number"
                    value={rows}
                    onChange={(e) => setRows(Number(e.target.value))}
                    helperText={`1–${max}; platform limit`}
                    slotProps={{ htmlInput: { min: 1, max, step: 1 } }}
                  />
                  <TextField
                    label="Random seed"
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                    helperText="0–4294967295"
                    slotProps={{
                      htmlInput: { min: 0, max: 4294967295, step: 1 },
                    }}
                  />
                </Stack>
                {isTabular && (
                  <details>
                    <summary>Advanced configuration</summary>
                    <Stack gap={3} sx={{ pt: 2 }}>
                      <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
                        <TextField
                          label="Holdout fraction"
                          type="number"
                          value={holdout}
                          onChange={(e) => setHoldout(Number(e.target.value))}
                          helperText="0–0.5. Default 0.2 yields advisory DCR overfitting."
                          slotProps={{
                            htmlInput: { min: 0, max: 0.5, step: 0.05 },
                          }}
                        />
                        <TextField
                          label="Split seed"
                          type="number"
                          value={splitSeed}
                          onChange={(e) => setSplitSeed(Number(e.target.value))}
                          slotProps={{ htmlInput: { min: 0, max: 4294967295 } }}
                        />
                      </Stack>
                      {engine !== "gaussian_copula" && (
                        <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
                          <TextField
                            label="Epochs"
                            type="number"
                            value={epochs}
                            onChange={(e) => setEpochs(Number(e.target.value))}
                            helperText={`1–${epochMax}`}
                            slotProps={{ htmlInput: { min: 1, max: epochMax } }}
                          />
                          <TextField
                            label="Batch size"
                            type="number"
                            value={batch}
                            onChange={(e) => setBatch(Number(e.target.value))}
                            helperText="10–500; multiple of 10"
                            slotProps={{
                              htmlInput: { min: 10, max: 500, step: 10 },
                            }}
                          />
                        </Stack>
                      )}
                      <TextField
                        select
                        label="Validation rule column"
                        value={ruleColumn}
                        onChange={(e) => {
                          setRuleColumn(e.target.value);
                          setMinimum("");
                          setMaximum("");
                        }}
                      >
                        <MenuItem value="">No additional rule</MenuItem>
                        {Object.entries(values)
                          .filter(([, v]) => v.role === "MODELLED")
                          .map(([name]) => (
                            <MenuItem key={name} value={name}>
                              {name}
                            </MenuItem>
                          ))}
                      </TextField>
                      {ruleColumn && (
                        <>
                          <FormControlLabel
                            label="Require non-null values"
                            control={
                              <Checkbox
                                checked={nonNull}
                                onChange={(e) => setNonNull(e.target.checked)}
                              />
                            }
                          />
                          {values[ruleColumn]?.semantic_type ===
                            "numerical" && (
                            <Stack
                              direction={{ xs: "column", sm: "row" }}
                              gap={2}
                            >
                              <TextField
                                label="Minimum value"
                                type="number"
                                value={minimum}
                                onChange={(e) => setMinimum(e.target.value)}
                              />
                              <TextField
                                label="Maximum value"
                                type="number"
                                value={maximum}
                                onChange={(e) => setMaximum(e.target.value)}
                              />
                            </Stack>
                          )}
                        </>
                      )}
                    </Stack>
                  </details>
                )}
                {!valid && (
                  <Alert severity="error">
                    Configuration is outside the displayed platform limits.
                  </Alert>
                )}
              </Stack>
            )}
            {step >= 4 && (
              <Stack gap={2}>
                <Facts
                  values={{
                    Dataset: d.name,
                    Engine: isTabular ? human(engine) : "ECG VAE",
                    Rows: rows,
                    Seed: seed,
                    "Modelled columns":
                      Object.entries(values)
                        .filter(([, v]) => v.role === "MODELLED")
                        .map(([k]) => k)
                        .join(", ") || "Signal windows",
                    "Identifier columns":
                      Object.entries(values)
                        .filter(([, v]) => v.role === "IDENTIFIER")
                        .map(([k]) => k)
                        .join(", ") || "None",
                    "Excluded columns":
                      Object.entries(values)
                        .filter(([, v]) => v.role === "EXCLUDED")
                        .map(([k]) => k)
                        .join(", ") || "None",
                    "Sensitive annotations":
                      Object.entries(values)
                        .filter(([, v]) =>
                          v.annotations.includes("SENSITIVE_ATTRIBUTE"),
                        )
                        .map(([k]) => k)
                        .join(", ") || "None",
                    "Holdout fraction": isTabular ? holdout : "Not applicable",
                    "Split seed": isTabular ? splitSeed : "Not applicable",
                  }}
                />
                {analysis?.warnings.map((w) => (
                  <Alert severity="warning" key={w}>
                    {w}
                  </Alert>
                ))}
                <Typography>
                  Generation does not establish privacy, utility or clinical
                  validity. A successful tabular run can be evaluated next.
                </Typography>
                {step === 5 && (
                  <Button
                    variant="contained"
                    disabled={
                      busy ||
                      !valid ||
                      !ready ||
                      !caps.data?.capabilities[
                        d.modality as "tabular" | "timeseries"
                      ].available
                    }
                    onClick={() => void submit()}
                  >
                    {busy ? "Submitting…" : "Submit synthetic run"}
                  </Button>
                )}
              </Stack>
            )}
          </Section>
          <Stack direction="row" justifyContent="space-between">
            <Button
              disabled={step === 0 || busy}
              onClick={() => setStep((s) => s - 1)}
            >
              Back
            </Button>
            {step < 5 && (
              <Button
                variant="contained"
                disabled={
                  busy || (step === 1 && !ready) || (step === 3 && !valid)
                }
                onClick={() => setStep((s) => s + 1)}
              >
                Continue
              </Button>
            )}
          </Stack>
        </>
      )}
    </>
  );
}
