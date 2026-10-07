import { useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Job, Evaluation, Page, Policy } from "../../types/domain";
import { Facts, PageTitle, Section, State } from "../../components/Workspace";
import { human } from "../../utils/format";
export default function EvaluationConfig() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const resource = useResource<Job>(`/api/v1/jobs/${jobId}`);
  const j = resource.data;
  const policies = useResource<Page<Policy>>(
    j ? `/api/v1/projects/${j.project_id}/release-policies?limit=100` : null,
  );
  const [profile, setProfile] = useState("BASIC");
  const [known, setKnown] = useState<string[]>([]);
  const [sensitive, setSensitive] = useState<string[]>([]);
  const [disclosure, setDisclosure] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [utility, setUtility] = useState(false);
  const [target, setTarget] = useState("");
  const [task, setTask] = useState("BINARY_CLASSIFICATION");
  const [group, setGroup] = useState("");
  const [independent, setIndependent] = useState(false);
  const [policy, setPolicy] = useState("");
  const [seed, setSeed] = useState(42);
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const columns = j?.configuration_json.columns ?? [];
  const modelled = columns.filter((c) => c.role === "MODELLED");
  const targets = modelled.filter(
    (c) =>
      c.name !== group &&
      (task === "REGRESSION"
        ? c.semantic_type === "numerical"
        : ["categorical", "boolean"].includes(c.semantic_type)),
  );
  const valid =
    Number.isInteger(seed) &&
    seed >= 0 &&
    seed <= 4294967295 &&
    (profile !== "FULL" ||
      ((!disclosure ||
        (confirm &&
          known.length > 0 &&
          sensitive.length > 0 &&
          !known.some((v) => sensitive.includes(v)))) &&
        (!utility || targets.some((c) => c.name === target))));
  function toggle(values: string[], value: string, set: (v: string[]) => void) {
    set(
      values.includes(value)
        ? values.filter((v) => v !== value)
        : [...values, value],
    );
    setConfirm(false);
    setReview(false);
  }
  async function submit() {
    setBusy(true);
    setError("");
    try {
      const continuous = modelled
        .filter(
          (c) =>
            ["numerical", "datetime"].includes(c.semantic_type) &&
            [...known, ...sensitive].includes(c.name),
        )
        .map((c) => c.name);
      const r = await api.post<Evaluation>(
        `/api/v1/generation-jobs/${jobId}/evaluations`,
        {
          profile,
          random_seed: seed,
          group_key: group || null,
          independent_rows: independent,
          release_policy_id: policy || null,
          ...(profile === "FULL" && disclosure
            ? {
                privacy: {
                  known_columns: known,
                  sensitive_columns: sensitive,
                  continuous_columns: continuous,
                  num_discrete_bins: 10,
                  estimated: false,
                },
              }
            : {}),
          ...(profile === "FULL" && utility
            ? { utility: { task, target } }
            : {}),
        },
      );
      navigate(`/evaluations/${r.data.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        title="Evaluate dataset"
        description="Select the evidence to compute for this successful synthetic run."
      />
      <State {...resource} />
      {error && <Alert severity="error">{error}</Alert>}
      {j &&
        (j.status !== "SUCCEEDED" || j.modality !== "tabular" ? (
          <Alert severity="info">
            Evaluation requires a successful tabular run.
          </Alert>
        ) : (
          <>
            <Link to={`/runs/${j.id}`}>Synthetic run {j.id.slice(0, 8)}</Link>
            <Section title="Evaluation profile">
              <Stack gap={2}>
                <TextField
                  select
                  label="Evaluation profile"
                  value={profile}
                  onChange={(e) => {
                    setProfile(e.target.value);
                    setReview(false);
                  }}
                >
                  {[
                    ["BASIC", "Basic · Structure, fidelity and exact overlap"],
                    ["STANDARD", "Standard · Basic plus DCR diagnostics"],
                    [
                      "FULL",
                      "Full · Standard plus configured disclosure and ML utility",
                    ],
                  ].map(([v, label]) => (
                    <MenuItem key={v} value={v}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
                <Typography>
                  Profiles choose computations. Some evidence may be
                  inapplicable; Full is not a universal quality grade.
                </Typography>
                <TextField
                  label="Evaluation seed"
                  type="number"
                  value={seed}
                  onChange={(e) => {
                    setSeed(Number(e.target.value));
                    setReview(false);
                  }}
                  helperText="0–4294967295"
                />
                <TextField
                  select
                  label="Entity group key"
                  value={group}
                  onChange={(e) => {
                    setGroup(e.target.value);
                    setIndependent(false);
                    setTarget("");
                    setReview(false);
                  }}
                >
                  <MenuItem value="">Undeclared</MenuItem>
                  {columns
                    .filter((c) => c.role !== "EXCLUDED")
                    .map((c) => (
                      <MenuItem key={c.name} value={c.name}>
                        {c.name}
                      </MenuItem>
                    ))}
                </TextField>
                <FormControlLabel
                  label="Each source row represents an independent entity"
                  control={
                    <Checkbox
                      checked={independent}
                      disabled={!!group}
                      onChange={(e) => {
                        setIndependent(e.target.checked);
                        setReview(false);
                      }}
                    />
                  }
                />
                <Alert severity="info">
                  Evaluation reconstructs the original split. Default 80/20 DCR
                  overfitting is advisory. Group overlap or undeclared
                  independence limits release-gating evidence.
                </Alert>
              </Stack>
            </Section>
            {profile === "FULL" && (
              <>
                <Section title="Privacy attack scenario">
                  <Stack gap={2}>
                    <FormControlLabel
                      label="Configure disclosure analysis"
                      control={
                        <Checkbox
                          checked={disclosure}
                          onChange={(e) => {
                            setDisclosure(e.target.checked);
                            setConfirm(false);
                            setReview(false);
                          }}
                        />
                      }
                    />
                    {disclosure && (
                      <>
                        <Typography>
                          Known attributes represent information an attacker is
                          assumed to know. Sensitive attributes represent
                          information the attacker attempts to infer.
                        </Typography>
                        <Button
                          onClick={() => {
                            setKnown(
                              modelled
                                .filter((c) =>
                                  c.annotations.includes("QUASI_IDENTIFIER"),
                                )
                                .map((c) => c.name),
                            );
                            setSensitive(
                              modelled
                                .filter((c) =>
                                  c.annotations.includes("SENSITIVE_ATTRIBUTE"),
                                )
                                .map((c) => c.name),
                            );
                            setConfirm(false);
                            setReview(false);
                          }}
                        >
                          Use annotation suggestions
                        </Button>
                        <Typography component="h3" variant="h6">
                          Known attributes
                        </Typography>
                        <Stack direction="row" flexWrap="wrap">
                          {modelled.map((c) => (
                            <FormControlLabel
                              key={c.name}
                              label={c.name}
                              control={
                                <Checkbox
                                  inputProps={{
                                    "aria-label": `Known ${c.name}`,
                                  }}
                                  checked={known.includes(c.name)}
                                  onChange={() =>
                                    toggle(known, c.name, setKnown)
                                  }
                                />
                              }
                            />
                          ))}
                        </Stack>
                        <Typography component="h3" variant="h6">
                          Sensitive attributes
                        </Typography>
                        <Stack direction="row" flexWrap="wrap">
                          {modelled.map((c) => (
                            <FormControlLabel
                              key={c.name}
                              label={c.name}
                              control={
                                <Checkbox
                                  inputProps={{
                                    "aria-label": `Sensitive ${c.name}`,
                                  }}
                                  checked={sensitive.includes(c.name)}
                                  onChange={() =>
                                    toggle(sensitive, c.name, setSensitive)
                                  }
                                />
                              }
                            />
                          ))}
                        </Stack>
                        <Typography>
                          Attack reference: original real holdout. Numerical and
                          datetime selections use 10 recorded discretization
                          bins; full bounded computation.
                        </Typography>
                        <FormControlLabel
                          label="Confirm selected known and sensitive attributes"
                          control={
                            <Checkbox
                              checked={confirm}
                              onChange={(e) => {
                                setConfirm(e.target.checked);
                                setReview(false);
                              }}
                            />
                          }
                        />
                      </>
                    )}
                  </Stack>
                </Section>
                <Section title="ML utility task">
                  <Stack gap={2}>
                    <FormControlLabel
                      label="Configure ML utility"
                      control={
                        <Checkbox
                          checked={utility}
                          onChange={(e) => {
                            setUtility(e.target.checked);
                            setReview(false);
                          }}
                        />
                      }
                    />
                    {utility && (
                      <>
                        <TextField
                          select
                          label="Task"
                          value={task}
                          onChange={(e) => {
                            setTask(e.target.value);
                            setTarget("");
                            setReview(false);
                          }}
                        >
                          {[
                            "BINARY_CLASSIFICATION",
                            "MULTICLASS_CLASSIFICATION",
                            "REGRESSION",
                          ].map((v) => (
                            <MenuItem key={v} value={v}>
                              {human(v)}
                            </MenuItem>
                          ))}
                        </TextField>
                        <TextField
                          select
                          label="Target column"
                          value={target}
                          onChange={(e) => {
                            setTarget(e.target.value);
                            setReview(false);
                          }}
                        >
                          <MenuItem value="">Select target</MenuItem>
                          {targets.map((c) => (
                            <MenuItem key={c.name} value={c.name}>
                              {c.name}
                            </MenuItem>
                          ))}
                        </TextField>
                        <Typography>
                          TSTR: train a model on synthetic data and evaluate it
                          on untouched real holdout data.
                        </Typography>
                        <Typography>
                          TRTR: train the same model on real training data and
                          evaluate it on the same holdout.
                        </Typography>
                        <Typography color="text.secondary">
                          Only modelled targets with compatible types appear.
                          Class cardinality and other data-dependent
                          requirements are validated by the platform.
                        </Typography>
                      </>
                    )}
                  </Stack>
                </Section>
              </>
            )}
            <Section title="Release policy">
              <Stack gap={2}>
                <State {...policies} />
                <TextField
                  select
                  label="Release policy version"
                  value={policy}
                  onChange={(e) => {
                    setPolicy(e.target.value);
                    setReview(false);
                  }}
                >
                  <MenuItem value="">No policy · Not evaluated</MenuItem>
                  {policies.data?.items.map((p) => (
                    <MenuItem key={p.id} value={p.id}>
                      {p.name} v{p.version}
                      {p.illustrative ? " · Illustrative" : ""}
                    </MenuItem>
                  ))}
                </TextField>
                <Link to={`/projects/${j.project_id}/policies`}>
                  View policies or create a new version
                </Link>
                <Typography>
                  Policy thresholds are organization/project-defined operational
                  criteria. MedSynth Guard does not treat them as universal
                  medical, legal or privacy standards.
                </Typography>
              </Stack>
            </Section>
            <Section title="Review and submit">
              {review ? (
                <Stack gap={3}>
                  <Facts
                    values={{
                      Run: j.id,
                      Profile: human(profile),
                      "Known attributes":
                        profile === "FULL" && disclosure
                          ? known.join(", ")
                          : "Not configured",
                      "Sensitive attributes":
                        profile === "FULL" && disclosure
                          ? sensitive.join(", ")
                          : "Not configured",
                      Utility:
                        profile === "FULL" && utility
                          ? `${human(task)} · ${target}`
                          : "Not configured",
                      Policy:
                        policies.data?.items.find((p) => p.id === policy)
                          ?.name ?? "None",
                      Seed: seed,
                    }}
                  />
                  <Button
                    variant="contained"
                    disabled={busy || !valid}
                    onClick={() => void submit()}
                  >
                    {busy ? "Submitting…" : "Submit evaluation"}
                  </Button>
                </Stack>
              ) : (
                <Button
                  variant="contained"
                  disabled={!valid}
                  onClick={() => setReview(true)}
                >
                  Review evaluation
                </Button>
              )}
            </Section>
          </>
        ))}
    </>
  );
}
