import React, { useState } from 'react';
import { Box, Button, Card, CardContent, TextField, Typography, Chip } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';

export const TimeSeriesGenerator = ({ onGenerate }: { onGenerate: (config: any, file: File) => void }) => {
  const [count, setCount] = useState(500);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleGenerateClick = () => {
    if (selectedFile) {
      onGenerate({ type: 'timeseries', count }, selectedFile);
    }
  };

  return (
    // The maxWidth has been removed from the Card
    <Card sx={{ mt: 2 }}>
      <CardContent sx={{ p: 4 }}>
        <Typography variant="h4" gutterBottom align="center">⏱️ Time-Series Data Generator</Typography>

        <Box sx={{ mb: 3, p: 2, border: '1px dashed grey', borderRadius: 1, textAlign: 'center' }}>
          <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
            Upload Time-Series CSV (Required)
            <input type="file" hidden onChange={handleFileChange} accept=".csv" />
          </Button>
          {selectedFile && (
            <Chip label={selectedFile.name} onDelete={() => setSelectedFile(null)} sx={{ mt: 2 }} />
          )}
        </Box>

        <TextField 
          label="Number of Sequences to Generate" 
          type="number" 
          variant="outlined"
          value={count} 
          onChange={(e) => setCount(parseInt(e.target.value))} 
          fullWidth sx={{ mb: 3 }} 
        />
        <Box sx={{ mt: 3, textAlign: 'center' }}>
          <Button variant="contained" color="primary" size="large" onClick={handleGenerateClick} disabled={!selectedFile}>
            Generate Sequences
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};