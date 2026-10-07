import {
  Alert,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from "@mui/material";

export function TabularGenerator() {
  return (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <Stack direction="row" spacing={2}>
            <Typography variant="h5">Clinical tabular data</Typography>
            <Chip label="Stable" color="success" />
          </Stack>
          <Typography>
            Use Synthetic Runs to select a registered dataset, review preflight
            and configure a real fitted model.
          </Typography>
          <Alert severity="info">
            Gaussian Copula is the stable default. CTGAN and TVAE are opt-in
            Beta. Evaluate successful runs to inspect separate fidelity, privacy
            diagnostics and task-specific utility evidence.
          </Alert>
        </Stack>
      </CardContent>
    </Card>
  );
}
