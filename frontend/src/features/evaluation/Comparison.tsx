import { useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  Stack,
  Typography,
} from "@mui/material";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type {
  Comparison as ComparisonResult,
  Evaluation,
  Page,
} from "../../types/domain";
import {
  DataTable,
  Empty,
  PageTitle,
  Pager,
  Section,
  State,
  Status,
} from "../../components/Workspace";
import { human, number } from "../../utils/format";
export default function Comparison() {
  const { projectId } = useParams();
  const [offset, setOffset] = useState(0);
  const resource = useResource<Page<Evaluation>>(
    `/api/v1/projects/${projectId}/evaluations?limit=20&offset=${offset}`,
  );
  const [ids, setIds] = useState<string[]>([]);
  const [result, setResult] = useState<ComparisonResult>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function compare() {
    setBusy(true);
    setError("");
    setResult(undefined);
    try {
      const r = await api.post<ComparisonResult>(
        `/api/v1/projects/${projectId}/evaluations/compare`,
        { evaluation_ids: ids },
      );
      setResult(r.data);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        title="Model comparison"
        description="Independent evidence across compatible evaluated runs. Selection order is preserved."
      />
      <Alert severity="info">
        Comparison requires the same source dataset/hash, schema, original
        split, profile, utility target/task, attack scenario, seeds, limits and
        policy version. Incompatible evaluations cannot be displayed as
        equivalent.
      </Alert>
      {error && (
        <Alert severity="warning">Comparison unavailable. {error}</Alert>
      )}
      <Section title="Select completed evaluations">
        <State {...resource} />
        {resource.data &&
          (resource.data.items.length ? (
            <Stack gap={1}>
              {resource.data.items.map((e) => (
                <Stack key={e.id} direction="row" gap={1}>
                  <FormControlLabel
                    label={`Compare ${e.id.slice(0, 8)}`}
                    control={
                      <Checkbox
                        checked={ids.includes(e.id)}
                        disabled={
                          e.status !== "SUCCEEDED" ||
                          (!ids.includes(e.id) && ids.length >= 10)
                        }
                        onChange={(event) => {
                          setResult(undefined);
                          setIds(
                            event.target.checked
                              ? [...ids, e.id]
                              : ids.filter((id) => id !== e.id),
                          );
                        }}
                      />
                    }
                  />
                  <Link to={`/evaluations/${e.id}`}>
                    Evaluation {e.id.slice(0, 8)}
                  </Link>
                  <Status value={e.status} />
                </Stack>
              ))}
              <Pager
                total={resource.data.total}
                offset={offset}
                onChange={setOffset}
              />
            </Stack>
          ) : (
            <Empty title="No evaluations yet">
              Evaluate successful runs with compatible settings to compare their
              evidence.
            </Empty>
          ))}
        <Button
          variant="contained"
          disabled={busy || ids.length < 2}
          sx={{ mt: 2 }}
          onClick={() => void compare()}
        >
          {busy ? "Checking compatibility…" : "Compare selected evaluations"}
        </Button>
      </Section>
      {result && (
        <Section title="Compatible evidence">
          <Typography sx={{ mb: 2 }}>
            No ranking or composite score is produced. Applicability accompanies
            each diagnostic.
          </Typography>
          <DataTable
            label="Independent model comparison"
            headers={[
              "Engine",
              "Training / sampling seconds",
              "Holdout shapes / pairs",
              "DCR baseline",
              "DCR overfitting",
              "Disclosure",
              "TRTR / TSTR",
              "Relative utility",
              "Release decision",
            ]}
            rows={result.rows.map((r) => [
              human(r.engine),
              `${number(r.results.generation_performance?.training_duration_seconds)} / ${number(r.results.generation_performance?.sampling_duration_seconds)}`,
              `${number(r.results.quality.holdout.properties?.["Column Shapes"]?.score)} / ${number(r.results.quality.holdout.properties?.["Column Pair Trends"]?.score)}`,
              `${number(r.results.privacy.dcr_baseline_protection.score)} · ${human(r.results.privacy.dcr_baseline_protection.applicability)}`,
              `${number(r.results.privacy.dcr_overfitting_protection.score)} · ${human(r.results.privacy.dcr_overfitting_protection.applicability)}`,
              `${number(r.results.privacy.disclosure_protection.score)} · ${human(r.results.privacy.disclosure_protection.applicability)}`,
              Object.keys(r.results.utility.comparisons ?? {})
                .map(
                  (k) =>
                    `${k}: ${number(r.results.utility.trtr?.[k])} / ${number(r.results.utility.tstr?.[k])}`,
                )
                .join("; ") || "Not configured",
              Object.entries(r.results.utility.comparisons ?? {})
                .map(
                  ([k, c]) => `${k}: ${c.ratio_semantics} ${number(c.ratio)}`,
                )
                .join("; ") || "Unavailable",
              <Status value={r.results.release.decision} />,
            ])}
          />
        </Section>
      )}
    </>
  );
}
