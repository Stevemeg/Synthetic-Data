import { useIdentity } from "../identity/context";
import { useState } from "react";
import { Alert, Button, Stack } from "@mui/material";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type { Dataset } from "../../types/domain";
import {
  Facts,
  Integrity,
  PageTitle,
  Section,
  State,
} from "../../components/Workspace";
import TabularConfiguration, {
  type Overrides,
  type Profile,
} from "../../components/TabularConfiguration";
import { date, human, number } from "../../utils/format";
import { inferredOverrides } from "../../utils/governance";
export default function DatasetDetail() {
  const { canEdit } = useIdentity();
  const { datasetId } = useParams();
  const resource = useResource<Dataset>(`/api/v1/datasets/${datasetId}`);
  const [profile, setProfile] = useState<Profile>();
  const [overrides, setOverrides] = useState<Overrides>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const dataset = resource.data;
  const analysis = profile ?? dataset?.metadata_json.tabular_profile;
  const values =
    overrides ??
    (analysis
      ? inferredOverrides(analysis, dataset?.metadata_json.governance_overrides)
      : {});
  async function preflight() {
    setBusy(true);
    setError("");
    try {
      const r = await api.post<Profile>(
        `/api/v1/datasets/${datasetId}/tabular/preflight`,
      );
      setProfile(r.data);
      setOverrides(
        inferredOverrides(r.data, dataset?.metadata_json.governance_overrides),
      );
      setMessage(
        "Preflight completed. Review advisory warnings and column roles.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      await api.put(`/api/v1/datasets/${datasetId}/tabular/governance`, {
        overrides: values,
      });
      setMessage(
        "Schema governance saved. New runs use this configuration for review.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <State {...resource} />
      {dataset && (
        <>
          <PageTitle
            title={dataset.name}
            description="Dataset identity, schema and governance. Source records are not previewed."
            action={
              <Button
                component={Link}
                to={`/datasets/${datasetId}/generate`}
                variant="contained"
                disabled={!canEdit}
              >
                Start synthesis
              </Button>
            }
          />
          <Link to={`/projects/${dataset.project_id}`}>Open project</Link>
          {error && <Alert severity="error">{error}</Alert>}
          {message && <Alert severity="success">{message}</Alert>}
          <Section title="Dataset overview">
            <Facts
              values={{
                Filename: dataset.original_filename,
                Modality: human(dataset.modality),
                Rows: dataset.row_count,
                Columns: dataset.column_count,
                Size: `${number(dataset.size_bytes)} bytes`,
                Registered: date(dataset.created_at),
              }}
            />
            <Integrity hash={dataset.sha256} />
          </Section>
          {dataset.modality === "tabular" ? (
            <>
              <Section title="Preflight review">
                <Stack gap={2}>
                  <Button
                    disabled={busy || !canEdit}
                    onClick={() => void preflight()}
                    variant="outlined"
                  >
                    Run preflight
                  </Button>
                  {analysis && (
                    <>
                      <Alert
                        severity={analysis.compatible ? "success" : "error"}
                      >
                        {analysis.compatible
                          ? "Dataset compatible for schema review"
                          : "Blocking: dataset is incompatible"}
                      </Alert>
                      <Facts
                        values={{
                          "Potential identifiers": analysis.columns.filter(
                            (c) => c.suggested_role === "IDENTIFIER",
                          ).length,
                          "Potential free-text": analysis.columns.filter(
                            (c) => c.possible_free_text,
                          ).length,
                          "High cardinality": analysis.columns.filter(
                            (c) => c.high_cardinality,
                          ).length,
                          "Constant fields": analysis.columns.filter(
                            (c) => c.constant,
                          ).length,
                          "Unsupported fields": analysis.columns.filter(
                            (c) =>
                              c.inferred_type === "unsupported" || c.all_null,
                          ).length,
                        }}
                      />
                    </>
                  )}
                </Stack>
              </Section>
              {analysis && (
                <Section title="Dataset schema">
                  <TabularConfiguration
                    profile={analysis}
                    readOnly={!canEdit}
                    overrides={values}
                    onChange={setOverrides}
                  />
                  <Button
                    sx={{ mt: 2 }}
                    disabled={busy || !canEdit}
                    onClick={() => void save()}
                    variant="contained"
                  >
                    Save governance
                  </Button>
                </Section>
              )}
            </>
          ) : (
            <Alert severity="info">
              ECG · Beta. Headerless signal samples followed by an ignored
              source label. Tabular schema governance and evaluation apply only
              to clinical tables.
            </Alert>
          )}
        </>
      )}
    </>
  );
}
