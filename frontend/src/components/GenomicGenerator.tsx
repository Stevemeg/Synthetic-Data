import React, { useState } from 'react';
import { Box, Button, Card, CardContent, TextField, Typography, Select, MenuItem, FormControl, InputLabel, Chip } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';

export const GenomicGenerator = ({ onGenerate }: { onGenerate: (config: any, file: File) => void }) => {
  const [count, setCount] = useState(100);
  const [length, setLength] = useState(150);
  const [format, setFormat] = useState('FASTA');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleGenerateClick = () => {
    if (selectedFile) {
      onGenerate({ type: 'genomic', count, length, format }, selectedFile);
    }
  };

  return (
    // The maxWidth has been removed from the Card
    <Card sx={{ mt: 2 }}>
      <CardContent sx={{ p: 4 }}>
        <Typography variant="h4" gutterBottom align="center">🧬 Genomic Data Generator</Typography>

        <Box sx={{ mb: 3, p: 2, border: '1px dashed grey', borderRadius: 1, textAlign: 'center' }}>
          <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
            Upload Source File (Required)
            <input type="file" hidden onChange={handleFileChange} />
          </Button>
          {selectedFile && (
            <Chip label={selectedFile.name} onDelete={() => setSelectedFile(null)} sx={{ mt: 2 }} />
          )}
        </Box>

        <TextField label="Number of Sequences" type="number" variant="outlined" value={count} onChange={(e) => setCount(parseInt(e.target.value))} fullWidth sx={{ mb: 3 }} />
        <TextField label="Sequence Length" type="number" variant="outlined" value={length} onChange={(e) => setLength(parseInt(e.target.value))} fullWidth sx={{ mb: 3 }} />
        <FormControl fullWidth>
          <InputLabel>Output Format</InputLabel>
          <Select variant="outlined" value={format} label="Output Format" onChange={(e) => setFormat(e.target.value)}>
            <MenuItem value="FASTA">FASTA</MenuItem>
            <MenuItem value="FASTQ">FASTQ</MenuItem>
          </Select>
        </FormControl>
        <Box sx={{ mt: 3, textAlign: 'center' }}>
          <Button variant="contained" color="primary" size="large" onClick={handleGenerateClick} disabled={!selectedFile}>
            Generate Genomic Data
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};