import {
  Alert,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";

export type Column = {
  name: string;
  inferred_type: string;
  suggested_role: string;
  null_percentage: number;
  unique_count: number;
  warnings: string[];
  possible_free_text: boolean;
  all_null: boolean;
  high_cardinality?: boolean;
  constant?: boolean;
  cardinality_ratio?: number;
};
export type Profile = {
  dataset_id: string;
  compatible: boolean;
  row_count: number;
  column_count: number;
  columns: Column[];
  warnings: string[];
};
export type Override = {
  role: string;
  semantic_type: string;
  annotations: string[];
  identifier_strategy?: string;
};
export type Overrides = Record<string, Override>;

export default function TabularConfiguration({
  profile,
  overrides,
  onChange,
  readOnly = false,
}: {
  profile: Profile;
  overrides: Overrides;
  onChange: (value: Overrides) => void;
  readOnly?: boolean;
}) {
  function update(name: string, patch: Partial<Override>) {
    if (readOnly) return;
    const value = { ...overrides[name], ...patch };
    if (value.role === "IDENTIFIER") {
      value.identifier_strategy = "synthetic_sequence";
      value.semantic_type = "categorical";
    } else delete value.identifier_strategy;
    onChange({ ...overrides, [name]: value });
  }
  return (
    <Stack spacing={2}>
      <Typography>
        {profile.row_count} source rows · {profile.column_count} columns
      </Typography>
      <Alert severity="warning">
        Automatic column inference is advisory and can be wrong. Review every
        role before submission. Source values are not shown.
      </Alert>
      {profile.warnings.map((w) => (
        <Alert severity="info" key={w}>
          {w}
        </Alert>
      ))}
      <TableContainer>
        <Table aria-label="Dataset schema governance">
          <TableHead>
            <TableRow>
              {[
                "Column",
                "Inferred type",
                "Role",
                "Type override",
                "Annotations",
                "Null %",
                "Distinct values",
                "Warnings",
              ].map((h) => (
                <TableCell key={h} scope="col">
                  {h}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {profile.columns.map((column) => {
              const selected = overrides[column.name];
              if (!selected) return null;
              return (
                <TableRow key={column.name}>
                  <TableCell component="th" scope="row">
                    {column.name}
                  </TableCell>
                  <TableCell>{column.inferred_type}</TableCell>
                  <TableCell>
                    <Tooltip
                      describeChild
                      title="Model: learn this field. Identifier: replace with a synthetic sequence. Exclude: omit from training and output."
                    >
                      <TextField
                        disabled={readOnly}
                        sx={{ minWidth: 130 }}
                        select
                        fullWidth
                        label="Role"
                        slotProps={{
                          select: {
                            SelectDisplayProps: {
                              "aria-label": `${column.name} role`,
                            },
                          },
                        }}
                        value={selected.role}
                        onChange={(e) =>
                          update(column.name, { role: e.target.value })
                        }
                      >
                        <MenuItem
                          value="MODELLED"
                          disabled={
                            column.possible_free_text ||
                            column.all_null ||
                            column.inferred_type === "unsupported"
                          }
                        >
                          Model
                        </MenuItem>
                        <MenuItem value="IDENTIFIER">Identifier</MenuItem>
                        <MenuItem value="EXCLUDED">Exclude</MenuItem>
                      </TextField>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <TextField
                      sx={{ minWidth: 140 }}
                      select
                      fullWidth
                      label="Type"
                      slotProps={{
                        select: {
                          SelectDisplayProps: {
                            "aria-label": `${column.name} type`,
                          },
                        },
                      }}
                      disabled={readOnly || selected.role !== "MODELLED"}
                      value={selected.semantic_type}
                      onChange={(e) =>
                        update(column.name, { semantic_type: e.target.value })
                      }
                    >
                      {["numerical", "categorical", "boolean", "datetime"].map(
                        (type) => (
                          <MenuItem key={type} value={type}>
                            {type}
                          </MenuItem>
                        ),
                      )}
                    </TextField>
                  </TableCell>
                  <TableCell>
                    <Stack>
                      {[
                        ["QUASI_IDENTIFIER", "Quasi-identifier"],
                        ["SENSITIVE_ATTRIBUTE", "Sensitive attribute"],
                      ].map(([value, label]) => (
                        <Tooltip
                          key={value}
                          title={
                            value === "QUASI_IDENTIFIER"
                              ? "An attribute that may be known externally. Suggests a known attribute for disclosure review."
                              : "An attribute whose disclosure is of concern. Suggests a sensitive attribute for disclosure review."
                          }
                        >
                          <FormControlLabel
                            label={label}
                            control={
                              <Checkbox
                                disabled={readOnly}
                                inputProps={{
                                  "aria-label": `${column.name} ${label}`,
                                }}
                                checked={selected.annotations.includes(value)}
                                onChange={(e) =>
                                  update(column.name, {
                                    annotations: e.target.checked
                                      ? [...selected.annotations, value]
                                      : selected.annotations.filter(
                                          (a) => a !== value,
                                        ),
                                  })
                                }
                              />
                            }
                          />
                        </Tooltip>
                      ))}
                    </Stack>
                  </TableCell>
                  <TableCell>{column.null_percentage}</TableCell>
                  <TableCell>{column.unique_count}</TableCell>
                  <TableCell sx={{ minWidth: 220 }}>
                    {selected.role === "IDENTIFIER" && (
                      <Typography variant="body2">
                        Info: source identifiers excluded from training. New
                        unique SYN-000001 sequences replace them.
                      </Typography>
                    )}
                    {column.warnings.map((w) => (
                      <Typography variant="body2" key={w}>
                        Warning: {w}
                      </Typography>
                    ))}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
