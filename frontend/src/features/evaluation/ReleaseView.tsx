import { Alert, Stack, Typography } from "@mui/material";
import type { Release } from "../../types/domain";
import { DataTable, Integrity, Status } from "../../components/Workspace";
import { human, number } from "../../utils/format";
import { requirement } from "../../utils/governance";
export default function ReleaseView({ value }: { value: Release }) {
  return (
    <Stack gap={2}>
      <Status value={value.decision} />
      <Alert severity="info">
        A policy pass means this dataset satisfied the configured policy
        version. It is not a guarantee of anonymity, regulatory compliance or
        clinical validity.
      </Alert>
      {value.policy && (
        <>
          <Typography>
            {value.policy.name} · Version {value.policy.version}
            {value.policy.illustrative ? " · Illustrative" : ""}
          </Typography>
          <Integrity hash={value.policy.policy_hash} />
        </>
      )}
      <DataTable
        label="Policy decision explanation"
        headers={["Rule", "Observed value", "Requirement", "Status", "Reason"]}
        rows={value.rules.map((r) => [
          human(r.metric),
          number(r.actual_value),
          requirement(r.threshold),
          <Status
            value={r.status}
            label={
              r.status === "PASS"
                ? "Passed"
                : r.status === "FAIL"
                  ? "Failed"
                  : undefined
            }
          />,
          `${human(r.metric_applicability)}. ${r.reason}`,
        ])}
      />
      {!value.rules.length && (
        <Typography>
          No release policy was selected. No approval is inferred.
        </Typography>
      )}
    </Stack>
  );
}
