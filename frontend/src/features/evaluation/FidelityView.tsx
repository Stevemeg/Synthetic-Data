import { useState } from "react";
import { Box, MenuItem, Stack, TextField, Typography } from "@mui/material";
import type { Summary } from "../../types/domain";
import { DataTable, Pager, Section, Status } from "../../components/Workspace";
import { number } from "../../utils/format";
export default function FidelityView({ summary }: { summary: Summary }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("score");
  const [offset, setOffset] = useState(0);
  const [pairOffset, setPairOffset] = useState(0);
  const [pairSort, setPairSort] = useState("score");
  const training = summary.quality.training;
  const holdout = summary.quality.holdout;
  const columns = (holdout.column_metrics ?? [])
    .filter(
      (c) =>
        c.Column.toLowerCase().includes(search.toLowerCase()) &&
        (filter === "all" ||
          (filter === "low" && c.Score != null && c.Score < 0.8) ||
          (filter === "numerical" && c.Metric === "KSComplement") ||
          (filter === "categorical" && c.Metric === "TVComplement")),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.Column.localeCompare(b.Column)
        : (a.Score ?? Infinity) - (b.Score ?? Infinity),
    );
  const pairs = [...(holdout.pair_metrics ?? [])].sort((a, b) =>
    pairSort === "name"
      ? a["Column 1"].localeCompare(b["Column 1"])
      : (a.Score ?? Infinity) - (b.Score ?? Infinity),
  );
  return (
    <Stack gap={3}>
      <Typography>
        Higher values indicate greater similarity under this metric. This is
        fidelity evidence, not privacy or clinical validity.
      </Typography>
      <Box className="summary-grid">
        {(["training", "holdout"] as const).map((partition) => (
          <Section
            key={partition}
            title={`${partition === "training" ? "Training" : "Holdout"} fidelity`}
          >
            {Object.entries(summary.quality[partition].properties ?? {}).map(
              ([name, m]) => (
                <Box key={name} sx={{ mb: 2 }}>
                  <Typography>
                    {name}: <strong>{number(m.score)}</strong>
                  </Typography>
                  <Box
                    aria-hidden
                    sx={{
                      height: 8,
                      bgcolor: "action.hover",
                      borderRadius: 1,
                      my: 1,
                    }}
                  >
                    <Box
                      sx={{
                        width: `${typeof m.score === "number" ? Math.max(0, Math.min(1, m.score)) * 100 : 0}%`,
                        height: "100%",
                        bgcolor: "primary.main",
                        borderRadius: 1,
                      }}
                    />
                  </Box>
                  <Status value={m.applicability} />
                </Box>
              ),
            )}
          </Section>
        ))}
      </Box>
      <details>
        <summary>Learn more about Column Shapes and Column Pair Trends</summary>
        <Typography>
          Column Shapes compare individual distributions. Column Pair Trends
          compare selected relationships between pairs of variables. Pairwise
          fidelity does not establish full joint-distribution equivalence. Bars
          use a fixed 0–1 scale; numeric values and applicability labels remain
          visible.
        </Typography>
      </details>
      <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
        <TextField
          label="Search columns"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <TextField
          select
          label="Column filter"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setOffset(0);
          }}
        >
          {[
            ["all", "All columns"],
            ["low", "Below 0.80 · display filter only"],
            ["numerical", "Numerical"],
            ["categorical", "Categorical"],
          ].map(([v, l]) => (
            <MenuItem value={v} key={v}>
              {l}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="Column sort"
          value={sort}
          onChange={(e) => {
            setSort(e.target.value);
            setOffset(0);
          }}
        >
          <MenuItem value="score">Holdout score ascending</MenuItem>
          <MenuItem value="name">Column name</MenuItem>
        </TextField>
      </Stack>
      <DataTable
        label="Column fidelity"
        headers={[
          "Column",
          "Type",
          "Metric",
          "Training score",
          "Holdout score",
          "Applicability",
        ]}
        rows={columns
          .slice(offset, offset + 20)
          .map((c) => [
            c.Column,
            c.Metric === "KSComplement" ? "Numerical" : "Categorical",
            c.Metric,
            number(
              training.column_metrics?.find((t) => t.Column === c.Column)
                ?.Score,
            ),
            number(c.Score),
            <Status value={c.applicability} />,
          ])}
      />
      <Pager offset={offset} total={columns.length} onChange={setOffset} />
      <Typography component="h3" variant="h6">
        Pairwise relationships · Holdout
      </Typography>
      <Typography>
        Selected variable pairs; full joint-distribution equivalence is not
        established.
      </Typography>
      <TextField
        select
        label="Relationship sort"
        value={pairSort}
        onChange={(e) => {
          setPairSort(e.target.value);
          setPairOffset(0);
        }}
      >
        <MenuItem value="score">Holdout score ascending</MenuItem>
        <MenuItem value="name">Variable name</MenuItem>
      </TextField>
      <DataTable
        label="Pairwise fidelity"
        headers={[
          "Variable 1",
          "Variable 2",
          "Metric",
          "Training score",
          "Holdout score",
          "Applicability",
        ]}
        rows={pairs
          .slice(pairOffset, pairOffset + 20)
          .map((p) => [
            p["Column 1"],
            p["Column 2"],
            p.Metric,
            number(
              training.pair_metrics?.find(
                (t) =>
                  t["Column 1"] === p["Column 1"] &&
                  t["Column 2"] === p["Column 2"],
              )?.Score,
            ),
            number(p.Score),
            <Status value={p.applicability} />,
          ])}
      />
      <Pager
        offset={pairOffset}
        total={pairs.length}
        onChange={setPairOffset}
      />
    </Stack>
  );
}
