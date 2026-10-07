import { Alert, Stack, Typography } from "@mui/material";
import { DataTable, Facts, Status } from "../../components/Workspace";
import type { Metric, Summary, Utility } from "../../types/domain";
import { human, number } from "../../utils/format";
export function Diagnostic({
  name,
  value,
  help,
}: {
  name: string;
  value: Metric;
  help: string;
}) {
  return (
    <Stack gap={1}>
      <Typography variant="h6" component="h3">
        {name}
      </Typography>
      <Facts
        values={{
          Score: number(value.score),
          Applicability: <Status value={value.applicability} />,
        }}
      />
      {value.applicability === "ADVISORY_ONLY" && (
        <Alert severity="warning">
          Advisory only. This score cannot satisfy a required numeric release
          rule.
        </Alert>
      )}
      {value.breakdown && (
        <DataTable
          label={`${name} breakdown`}
          headers={["Measure", "Value"]}
          rows={Object.entries(value.breakdown).flatMap(([k, v]) =>
            v == null || typeof v === "number"
              ? [[human(k), number(v)]]
              : Object.entries(v).map(([name, measure]) => [
                  (
                    {
                      synthetic_data: "Synthetic median DCR",
                      random_data_baseline: "Baseline median DCR",
                      closer_to_training: "Closer-to-training fraction",
                      closer_to_holdout: "Closer-to-holdout fraction",
                    } as Record<string, string>
                  )[name] ?? `${human(k)}: ${human(name)}`,
                  number(measure),
                ]),
          )}
        />
      )}
      <details>
        <summary>Learn more about {name}</summary>
        <Typography>{help}</Typography>
      </details>
      {value.warnings?.map((w) => (
        <Typography key={w} variant="body2" color="text.secondary">
          Warning: {w}
        </Typography>
      ))}
    </Stack>
  );
}
export function PrivacyView({
  summary,
  rows,
}: {
  summary: Summary;
  rows?: number;
}) {
  const p = summary.privacy;
  return (
    <Stack gap={4}>
      <Typography component="h3" variant="h6">
        Exact overlap
      </Typography>
      <Typography>
        Matching generated rows:{" "}
        {p.exact_training.exact_matching_generated_rows} /{" "}
        {rows ?? summary.structural.produced_rows ?? "not recorded"} · Fraction:{" "}
        {number(p.exact_training.exact_match_fraction)}
      </Typography>
      <Typography>
        Exact matches are one possible memorization signal. Zero exact matches
        do not prove anonymity.
      </Typography>
      <Diagnostic
        name="DCR Baseline Protection"
        value={p.dcr_baseline_protection}
        help="Distance to closest record (DCR) compares synthetic-to-training distances with a random baseline. It covers selected distance behavior, not every disclosure risk."
      />
      <Diagnostic
        name="DCR Overfitting Protection"
        value={p.dcr_overfitting_protection}
        help="Compares how often generated rows are closer to training than untouched holdout. Comparable reference sizes and assessed entity independence are required by this platform for release gating. This is not a re-identification probability."
      />
      <Facts
        values={{
          "Train / holdout ratio": number(
            p.dcr_overfitting_protection.methodology?.train_validation_ratio,
          ),
          "Release gating eligible": p.dcr_overfitting_protection.methodology
            ?.gating_eligible
            ? "Yes"
            : "No",
        }}
      />
      <Diagnostic
        name="Disclosure Protection"
        value={p.disclosure_protection}
        help="Categorical attribution probability (CAP) estimates inference of selected sensitive attributes using assumed known attributes. CAP and baseline protection apply only to this configured scenario."
      />
      <Facts
        values={{
          "Known attributes":
            p.disclosure_protection.configuration?.known_columns.join(", ") ||
            "Not configured",
          "Sensitive attributes":
            p.disclosure_protection.configuration?.sensitive_columns.join(
              ", ",
            ) || "Not configured",
          Method:
            p.disclosure_protection.configuration?.computation_method ??
            "Not recorded",
          Reference: human(
            p.disclosure_protection.real_partition ?? "NOT_APPLICABLE",
          ),
        }}
      />
    </Stack>
  );
}
export function UtilityView({ value }: { value: Utility }) {
  return (
    <Stack gap={2}>
      <Facts
        values={{
          Task: value.task ? human(value.task) : "Not configured",
          Target: value.target ?? "Not configured",
          Applicability: <Status value={value.applicability} />,
        }}
      />
      <Typography>
        TRTR trains on real training data. TSTR trains on synthetic data. Both
        evaluate on the same untouched real holdout.
      </Typography>
      <DataTable
        label="TRTR and TSTR utility"
        headers={[
          "Metric",
          "Direction",
          "TRTR",
          "TSTR",
          "TSTR minus TRTR",
          "Relative comparison",
        ]}
        rows={Object.entries(value.comparisons ?? {}).map(([name, c]) => [
          name === "r2" ? "R²" : name.toUpperCase(),
          ["mae", "rmse"].includes(name)
            ? "Lower is better"
            : "Higher is better",
          number(value.trtr?.[name]),
          number(value.tstr?.[name]),
          number(c.absolute_delta),
          `${c.ratio_semantics}: ${number(c.ratio)}`,
        ])}
      />
      {value.task === "BINARY_CLASSIFICATION" && (
        <Typography>
          TSTR/TRTR F1 ratio: {number(value.comparisons?.f1?.ratio)}
        </Typography>
      )}
      {!value.task && (
        <Typography>
          No utility task was configured. No value is inferred.
        </Typography>
      )}
      {value.warnings?.map((w) => (
        <Alert key={w} severity="warning">
          {w}
        </Alert>
      ))}
    </Stack>
  );
}
