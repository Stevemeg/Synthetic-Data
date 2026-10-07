import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from "@mui/material";

export function GenomicGenerator() {
  return (
    <Card>
      <CardContent>
        <Stack spacing={3}>
          <Stack direction="row" spacing={2}>
            <Typography variant="h5">Genomics lab</Typography>
            <Chip label="Unavailable" />
          </Stack>
          <Alert severity="info">Unavailable. Research roadmap only.</Alert>
          <Typography>
            The random-value placeholder was removed. No genomic synthesis
            model, biological validation, FASTA, or FASTQ export is implemented.
          </Typography>
          <Button variant="contained" disabled>
            Generation unavailable
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
