import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import type { Activity, Artifact, Structural } from "../types/domain";
import { date, human, number } from "../utils/format";
import { downloadArtifact, errorMessage } from "../api/client";
import { useState } from "react";
export function Status({ value, label }: { value: string; label?: string }) {
  const color = ["SUCCEEDED", "PASS", "READY", "Stable"].includes(value)
    ? "success"
    : ["FAILED", "FAIL"].includes(value)
      ? "error"
      : [
            "REVIEW_REQUIRED",
            "ADVISORY_ONLY",
            "INSUFFICIENT_DATA",
            "Experimental",
          ].includes(value)
        ? "warning"
        : ["RUNNING", "QUEUED", "Beta"].includes(value)
          ? "info"
          : "default";
  return (
    <Chip
      sx={{ alignSelf: "flex-start", maxWidth: "100%" }}
      size="small"
      label={label ?? human(value)}
      color={color}
      variant="outlined"
    />
  );
}
export function PageTitle({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Stack
      direction={{ xs: "column", sm: "row" }}
      justifyContent="space-between"
      gap={2}
      alignItems={{ sm: "center" }}
    >
      <Box>
        <Typography variant="h4" component="h1">
          {title}
        </Typography>
        {description && (
          <Typography color="text.secondary" sx={{ mt: 1 }}>
            {description}
          </Typography>
        )}
      </Box>
      {action && <Box sx={{ flexShrink: 0 }}>{action}</Box>}
    </Stack>
  );
}
export function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Card component="section">
      <CardContent>
        <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
          {title}
        </Typography>
        {children}
      </CardContent>
    </Card>
  );
}
export function State({
  loading,
  error,
  reload,
}: {
  loading: boolean;
  error: string;
  reload: () => void;
}) {
  if (error)
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" onClick={reload}>
            Retry
          </Button>
        }
      >
        {error}
      </Alert>
    );
  return loading ? (
    <Box role="status" sx={{ p: 4, display: "flex", gap: 2 }}>
      <CircularProgress size={24} aria-label="Loading workspace" />
      Loading workspace…
    </Box>
  ) : null;
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Box sx={{ py: 4, textAlign: "center" }}>
      <Typography variant="h6">{title}</Typography>
      <Typography color="text.secondary">{children}</Typography>
    </Box>
  );
}
export function Pager({
  offset,
  total,
  onChange,
}: {
  offset: number;
  total: number;
  onChange: (n: number) => void;
}) {
  return (
    <Stack
      direction="row"
      alignItems="center"
      gap={1}
      justifyContent="flex-end"
    >
      <Typography variant="body2">
        {total ? offset + 1 : 0}–{Math.min(offset + 20, total)} of {total}
      </Typography>
      <Button
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - 20))}
      >
        Previous
      </Button>
      <Button
        disabled={offset + 20 >= total}
        onClick={() => onChange(offset + 20)}
      >
        Next
      </Button>
    </Stack>
  );
}
export function DataTable({
  label,
  headers,
  rows,
}: {
  label: string;
  headers: string[];
  rows: ReactNode[][];
}) {
  return (
    <TableContainer>
      <Table aria-label={label} size="small">
        <TableHead>
          <TableRow>
            {headers.map((h) => (
              <TableCell key={h} scope="col">
                {h}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              {row.map((cell, j) => (
                <TableCell
                  key={j}
                  {...(j === 0 ? { component: "th", scope: "row" } : {})}
                >
                  {cell}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
export function Facts({ values }: { values: Record<string, ReactNode> }) {
  return (
    <Box component="dl" className="facts">
      {Object.entries(values).map(([name, value]) => (
        <Box key={name}>
          <Typography component="dt" variant="body2" color="text.secondary">
            {name}
          </Typography>
          <Typography
            component="dd"
            sx={{ m: 0, mt: 0.5, overflowWrap: "anywhere", fontWeight: 600 }}
          >
            {value}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
export function Integrity({ hash }: { hash: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Box>
      <details>
        <summary>SHA-256: {hash.slice(0, 12)}…</summary>
        <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>
          {hash}
        </Typography>
        <Button
          onClick={() => {
            void navigator.clipboard
              .writeText(hash)
              .then(() => setCopied(true));
          }}
        >
          {copied ? "Copied" : "Copy hash"}
        </Button>
      </details>
    </Box>
  );
}
export function Artifacts({ items }: { items: Artifact[] }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  return (
    <Stack spacing={2}>
      {error && <Alert severity="error">{error}</Alert>}
      {!items.length ? (
        <Empty title="No artifacts yet">
          Artifacts appear after successful publication.
        </Empty>
      ) : (
        <DataTable
          label="Registered artifacts"
          headers={["Artifact", "Size", "Integrity", "Export"]}
          rows={items.map((a) => [
            human(a.artifact_type),
            `${number(a.size_bytes)} bytes`,
            <Integrity hash={a.sha256} />,
            <Button
              disabled={!a.downloadable || !!busy}
              onClick={async () => {
                setBusy(a.id);
                setError("");
                try {
                  await downloadArtifact(a.id, a.filename);
                } catch (e) {
                  setError(errorMessage(e));
                } finally {
                  setBusy("");
                }
              }}
            >
              {!a.downloadable
                ? "Model download restricted"
                : busy === a.id
                  ? "Downloading…"
                  : `Download ${human(a.artifact_type)}`}
            </Button>,
          ])}
        />
      )}
    </Stack>
  );
}
export function StructuralView({ value }: { value?: Structural }) {
  if (!value)
    return (
      <Empty title="Validation not available">
        Structural evidence appears after validation.
      </Empty>
    );
  return (
    <Stack gap={2}>
      <Alert severity={value.passed ? "success" : "error"}>
        {value.passed ? "Passed" : "Failed"} structural validation. This checks
        structure and configured rules.
      </Alert>
      <Facts
        values={{
          "Requested / produced rows": `${value.requested_rows ?? "—"} / ${value.produced_rows ?? "—"}`,
          "Schema order":
            value.column_order_valid == null
              ? "Not recorded"
              : value.column_order_valid
                ? "Passed"
                : "Failed",
          "Identifier collisions":
            value.identifier_collisions?.reduce((n, v) => n + v.count, 0) ??
            "Not recorded",
          "Excluded columns absent":
            value.excluded_columns_absent == null
              ? "Not recorded"
              : String(value.excluded_columns_absent),
        }}
      />
      <DataTable
        label="Structural issues"
        headers={["Check", "Details"]}
        rows={[
          ["Missing columns", value.missing_columns?.join(", ") || "None"],
          [
            "Unexpected columns",
            value.unexpected_columns?.join(", ") || "None",
          ],
          ["Type mismatches", value.dtype_mismatches?.join(", ") || "None"],
          [
            "Nullability",
            value.nullability_violations
              ?.map((v) => `${v.column}: ${v.count}`)
              .join("; ") || "None",
          ],
          [
            "Rule violations",
            value.rule_violations
              ?.map((v) => `${v.column}: ${human(v.rule)} (${v.count})`)
              .join("; ") || "None",
          ],
        ]}
      />
    </Stack>
  );
}
export function ActivityView({ items }: { items: Activity[] }) {
  return !items.length ? (
    <Empty title="No recorded activity">
      Activity will appear as work proceeds.
    </Empty>
  ) : (
    <DataTable
      label="Recorded activity"
      headers={["Event", "Actor", "Time"]}
      rows={items.map((a) => [
        human(a.event_type),
        a.actor === "anonymous" ? "Unauthenticated caller" : a.actor === "user" ? <Tooltip title={`User ${a.user_id || "unavailable"}${a.request_id ? ` · Request ${a.request_id}` : ""}`}><span>Authenticated user</span></Tooltip> : a.actor === "worker" ? "Worker" : "System",
        date(a.created_at),
      ])}
    />
  );
}
export const ResourceLink = ({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) => <Link to={to}>{children}</Link>;
