import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type { GeneratorProps } from "../types";

export function GenerationForm({
  kind,
  onGenerate,
  loading,
  capability,
  maxCount,
  maxUploadMb,
}: GeneratorProps & { kind: "timeseries" | "imaging" }) {
  const imaging = kind === "imaging";
  const [count, setCount] = useState(imaging ? "10" : "100");
  const [seed, setSeed] = useState("42");
  const [modality, setModality] = useState("MRI");
  const [file, setFile] = useState<File>();
  const [fileError, setFileError] = useState("");
  const countNumber = Number(count);
  const seedNumber = Number(seed);
  const validCount =
    count.trim() !== "" &&
    Number.isInteger(countNumber) &&
    countNumber >= 1 &&
    countNumber <= maxCount;
  const validSeed =
    seed.trim() !== "" &&
    Number.isInteger(seedNumber) &&
    seedNumber >= 0 &&
    seedNumber <= 4294967295;
  const available = capability?.available ?? false;
  return (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <Stack direction="row" spacing={2} alignItems="center">
            <Typography variant="h5">
              {imaging ? "Medical imaging lab" : "ECG heartbeat generation"}
            </Typography>
            <Chip
              label={imaging ? "Experimental" : "Beta"}
              color={imaging ? "warning" : "info"}
            />
          </Stack>
          <Typography>
            {imaging
              ? "Generate 64 × 64 RGB PNG samples from preserved DCGAN checkpoints. The ZIP contains every requested image. No source conditioning or clinical validation is provided."
              : "Train a CPU VAE on extracted heartbeat windows. Upload a headerless CSV with 96–10000 numeric signal samples per row, followed by a source label. Labels are ignored; generated windows are unlabeled and normalized to [0, 1]. Sampling rate and training epochs are configured by the server."}
          </Typography>
          {!available && (
            <Alert severity="info">
              {capability?.reason ?? "Checking backend availability…"}
            </Alert>
          )}
          {imaging ? (
            <TextField
              select
              label="Checkpoint modality"
              value={modality}
              onChange={(e) => setModality(e.target.value)}
              disabled={loading || !available}
            >
              <MenuItem value="MRI">Brain MRI</MenuItem>
              <MenuItem value="X-Ray">Chest X-Ray</MenuItem>
              <MenuItem value="Skin">Skin Lesion</MenuItem>
            </TextField>
          ) : (
            <Stack direction="row" spacing={2} alignItems="center">
              <Button
                component="label"
                variant="outlined"
                disabled={loading || !available}
              >
                Choose ECG CSV
                <input
                  hidden
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(e) => {
                    const selected = e.target.files?.[0];
                    setFile(undefined);
                    setFileError("");
                    if (!selected) return;
                    if (!selected.name.toLowerCase().endsWith(".csv"))
                      setFileError("Choose a .csv file.");
                    else if (
                      !selected.size ||
                      selected.size > maxUploadMb * 1024 ** 2
                    )
                      setFileError(
                        `Choose a nonempty CSV smaller than ${maxUploadMb} MB (including request overhead).`,
                      );
                    else setFile(selected);
                    e.target.value = "";
                  }}
                />
              </Button>
              {file && (
                <Chip
                  label={file.name}
                  onDelete={loading ? undefined : () => setFile(undefined)}
                />
              )}
            </Stack>
          )}
          {fileError && <Alert severity="error">{fileError}</Alert>}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              fullWidth
              label={imaging ? "Image count" : "Generated heartbeat count"}
              type="number"
              value={count}
              onChange={(e) => setCount(e.target.value)}
              disabled={loading || !available}
              error={!validCount}
              helperText={`Integer from 1 to ${maxCount}`}
              slotProps={{ htmlInput: { min: 1, max: maxCount, step: 1 } }}
            />
            <TextField
              fullWidth
              label="Random seed"
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              disabled={loading || !available}
              error={!validSeed}
              helperText="Integer from 0 to 4294967295"
              slotProps={{ htmlInput: { min: 0, max: 4294967295, step: 1 } }}
            />
          </Stack>
          <Alert severity="warning">
            Privacy risk, diagnostic validity, and ML utility have not been
            measured. Review generated artifacts before any release.
          </Alert>
          <Button
            variant="contained"
            disabled={
              loading ||
              !available ||
              !validCount ||
              !validSeed ||
              (!imaging && !file)
            }
            onClick={() => {
              void onGenerate(
                {
                  type: kind,
                  count: countNumber,
                  seed: seedNumber,
                  ...(imaging ? { modality } : {}),
                },
                file,
              );
            }}
          >
            {loading ? "Generating…" : "Run generation"}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
