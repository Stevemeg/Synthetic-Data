import { useIdentity } from "../identity/context";
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
import { useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Page, Policy } from "../../types/domain";
import {
  DataTable,
  Empty,
  Integrity,
  PageTitle,
  Section,
  State,
} from "../../components/Workspace";
import { date, human } from "../../utils/format";
import { requirement } from "../../utils/governance";
const policyNotice =
  "Policy thresholds are organization/project-defined operational criteria. MedSynth Guard does not treat them as universal medical, legal or privacy standards.";
const metrics = [
  "structural_validation",
  "training_column_shapes",
  "training_column_pair_trends",
  "holdout_column_shapes",
  "holdout_column_pair_trends",
  "exact_training_match_fraction",
  "dcr_baseline_protection",
  "dcr_overfitting_protection",
  "dcr_overfitting_gating_eligible",
  "disclosure_protection",
  "tstr_trtr_ratio",
  "group_leakage_free",
];
type BuilderRule = {
  metric: string;
  operator: string;
  threshold: string;
  upperThreshold?: string;
  required: boolean;
  when: string;
};
export default function Policies() {
  const { isOwner } = useIdentity();
  const { projectId } = useParams();
  const resource = useResource<Page<Policy>>(
    `/api/v1/projects/${projectId}/release-policies?limit=100`,
  );
  const usage = useResource<Record<string, number>>(
    `/api/v1/workspace/projects/${projectId}/policy-usage`,
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [version, setVersion] = useState(1);
  const [illustrative, setIllustrative] = useState(false);
  const [rules, setRules] = useState<BuilderRule[]>([
    {
      metric: "structural_validation",
      operator: "equals",
      threshold: "true",
      required: true,
      when: "ALWAYS",
    },
  ]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  function update(i: number, patch: Partial<BuilderRule>) {
    setRules(rules.map((r, n) => (n === i ? { ...r, ...patch } : r)));
  }
  const booleanMetric = (m: string) =>
    [
      "structural_validation",
      "dcr_overfitting_gating_eligible",
      "group_leakage_free",
    ].includes(m);
  const valid =
    name.trim() &&
    Number.isInteger(version) &&
    version >= 1 &&
    version <= 100000 &&
    rules.length > 0 &&
    new Set(rules.map((r) => r.metric)).size === rules.length &&
    rules.every(
      (r) =>
        booleanMetric(r.metric) ||
        (r.threshold.trim() !== "" &&
          Number.isFinite(Number(r.threshold)) &&
          (r.operator !== "range" ||
            (r.upperThreshold?.trim() !== "" &&
              r.upperThreshold != null &&
              Number.isFinite(Number(r.upperThreshold)) &&
              Number(r.upperThreshold) >= Number(r.threshold)))),
    );
  async function create() {
    setBusy(true);
    setError("");
    try {
      await api.post(`/api/v1/projects/${projectId}/release-policies`, {
        name: name.trim(),
        description,
        version,
        illustrative,
        rules: Object.fromEntries(
          rules.map((r) => [
            r.metric,
            {
              required: r.required,
              when: r.when,
              ...(r.operator === "range" && !booleanMetric(r.metric)
                ? {
                    minimum: Number(r.threshold),
                    maximum: Number(r.upperThreshold),
                  }
                : {
                    [booleanMetric(r.metric) ? "equals" : r.operator]:
                      booleanMetric(r.metric)
                        ? r.threshold === "true"
                        : Number(r.threshold),
                  }),
            },
          ]),
        ),
      });
      resource.reload();
      setMessage("Immutable policy version created.");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        title="Release policies"
        description="Project-defined, immutable versions. Changes create a new version."
      />
      {error && <Alert severity="error">{error}</Alert>}
      {message && <Alert severity="success">{message}</Alert>}
      <Alert severity="info">{policyNotice}</Alert>
      <Section title="Policy versions">
        <State {...resource} />
        {resource.data &&
          (!resource.data.items.length ? (
            <Empty title="No policies yet">
              Create explicit operational criteria for this project.
            </Empty>
          ) : (
            <Stack gap={3}>
              {resource.data.items.map((p) => (
                <Stack gap={1} key={p.id}>
                  <Typography variant="h6" component="h3">
                    {p.name} · Version {p.version}
                  </Typography>
                  <Typography variant="body2">
                    Created {date(p.created_at)} · Used by{" "}
                    {usage.data?.[p.id] ?? "…"} evaluations · Immutable
                  </Typography>
                  {p.illustrative && (
                    <Alert severity="warning">
                      Example operational thresholds for demonstration only. Not
                      a medical, legal, regulatory or privacy standard.
                    </Alert>
                  )}
                  <Integrity hash={p.policy_hash} />
                  <DataTable
                    label={`${p.name} version ${p.version} rules`}
                    headers={["Metric", "Requirement", "Condition"]}
                    rows={Object.entries(p.rules).map(([m, r]) => [
                      human(m),
                      requirement(r),
                      human(r.when ?? "ALWAYS"),
                    ])}
                  />
                  <Button
                    disabled={!isOwner}
                    onClick={() => {
                      setName(p.name);
                      setDescription(p.description);
                      setVersion(
                        Math.max(
                          ...(resource.data?.items
                            .filter((v) => v.name === p.name)
                            .map((v) => v.version) ?? [p.version]),
                        ) + 1,
                      );
                      setIllustrative(p.illustrative);
                      setRules(
                        Object.entries(p.rules).map(([metric, r]) => ({
                          metric,
                          operator:
                            r.equals != null
                              ? "equals"
                              : r.minimum != null && r.maximum != null
                                ? "range"
                                : r.minimum != null
                                  ? "minimum"
                                  : "maximum",
                          threshold: String(r.equals ?? r.minimum ?? r.maximum),
                          upperThreshold:
                            r.maximum != null ? String(r.maximum) : undefined,
                          required: r.required,
                          when: r.when ?? "ALWAYS",
                        })),
                      );
                      document
                        .getElementById("policy-builder")
                        ?.scrollIntoView();
                    }}
                  >
                    Create new version
                  </Button>
                </Stack>
              ))}
            </Stack>
          ))}
      </Section>
      <Section title="Create immutable policy version">
        <Stack gap={3} id="policy-builder">
          <TextField
            label="Policy name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            slotProps={{ htmlInput: { maxLength: 120 } }}
          />
          <TextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
          />
          <TextField
            label="Version"
            type="number"
            value={version}
            onChange={(e) => setVersion(Number(e.target.value))}
            slotProps={{ htmlInput: { min: 1, max: 100000 } }}
          />
          {rules.map((r, i) => (
            <Stack key={i} direction={{ xs: "column", lg: "row" }} gap={2}>
              <TextField
                select
                fullWidth
                label={`Rule ${i + 1} metric`}
                value={r.metric}
                onChange={(e) =>
                  update(i, {
                    metric: e.target.value,
                    operator: booleanMetric(e.target.value)
                      ? "equals"
                      : "minimum",
                    threshold: booleanMetric(e.target.value) ? "true" : "0.8",
                  })
                }
              >
                {metrics.map((m) => (
                  <MenuItem
                    key={m}
                    value={m}
                    disabled={rules.some((v, n) => n !== i && v.metric === m)}
                  >
                    {human(m)}
                  </MenuItem>
                ))}
              </TextField>
              {booleanMetric(r.metric) ? (
                <TextField
                  select
                  fullWidth
                  label={`Rule ${i + 1} expected value`}
                  value={r.threshold}
                  onChange={(e) => update(i, { threshold: e.target.value })}
                >
                  <MenuItem value="true">Passed / Yes</MenuItem>
                  <MenuItem value="false">Failed / No</MenuItem>
                </TextField>
              ) : (
                <>
                  <TextField
                    select
                    fullWidth
                    label={`Rule ${i + 1} operator`}
                    value={r.operator}
                    onChange={(e) => update(i, { operator: e.target.value })}
                  >
                    <MenuItem value="minimum">At least ≥</MenuItem>
                    <MenuItem value="maximum">At most ≤</MenuItem>
                    <MenuItem value="range">Between (inclusive)</MenuItem>
                  </TextField>
                  <TextField
                    fullWidth
                    label={`Rule ${i + 1} threshold`}
                    type="number"
                    value={r.threshold}
                    onChange={(e) => update(i, { threshold: e.target.value })}
                  />
                  {r.operator === "range" && (
                    <TextField
                      fullWidth
                      label={`Rule ${i + 1} upper threshold`}
                      type="number"
                      value={r.upperThreshold ?? ""}
                      onChange={(e) =>
                        update(i, { upperThreshold: e.target.value })
                      }
                    />
                  )}
                </>
              )}
              <TextField
                select
                fullWidth
                label={`Rule ${i + 1} condition`}
                value={r.when}
                onChange={(e) => update(i, { when: e.target.value })}
              >
                {["ALWAYS", "DISCLOSURE_CONFIGURED", "UTILITY_CONFIGURED"].map(
                  (v) => (
                    <MenuItem key={v} value={v}>
                      {human(v)}
                    </MenuItem>
                  ),
                )}
              </TextField>
              <FormControlLabel
                label={`Rule ${i + 1} required`}
                control={
                  <Checkbox
                    checked={r.required}
                    onChange={(e) => update(i, { required: e.target.checked })}
                  />
                }
              />
              <Button
                disabled={rules.length === 1}
                onClick={() => setRules(rules.filter((_, n) => n !== i))}
              >
                Remove
              </Button>
            </Stack>
          ))}
          <Button
            disabled={rules.length >= metrics.length}
            onClick={() =>
              setRules([
                ...rules,
                {
                  metric: metrics.find(
                    (m) => !rules.some((r) => r.metric === m),
                  )!,
                  operator: "minimum",
                  threshold: "0.8",
                  required: true,
                  when: "ALWAYS",
                },
              ])
            }
          >
            Add rule
          </Button>
          <FormControlLabel
            label="Illustrative demonstration policy"
            control={
              <Checkbox
                checked={illustrative}
                onChange={(e) => setIllustrative(e.target.checked)}
              />
            }
          />
          <Typography>{policyNotice}</Typography>
          <Button
            variant="contained"
            disabled={!isOwner || !valid || busy}
            onClick={() => void create()}
          >
            {busy ? "Creating…" : "Create policy version"}
          </Button>
        </Stack>
      </Section>
    </>
  );
}
