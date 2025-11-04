import React, { useState } from 'react';
import { Box, Button, Card, CardContent, TextField, Typography, Select, MenuItem, FormControl, InputLabel, Chip } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';

export const TabularGenerator = ({ onGenerate }: { onGenerate: (config: any, file: File) => void }) => {
  const [rowCount, setRowCount] = useState(100);
  const [dataset, setDataset] = useState('Heart Disease');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleGenerateClick = () => {
    if (selectedFile) {
      onGenerate({ type: 'tabular', rowCount, dataset }, selectedFile);
    }
  };
  
  // The form is disabled until a file is selected
  const isFormDisabled = !selectedFile;

  return (
    <Card sx={{ mt: 2 }}> 
      <CardContent sx={{ p: 4 }}>
        <Typography variant="h4" gutterBottom align="center">📊 Tabular Data Generator</Typography>
        
        {/* Step 1: File Upload */}
        <Box sx={{ mb: 3, p: 2, border: '1px dashed grey', borderRadius: 1, textAlign: 'center' }}>
          <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
            Upload Source File
            <input type="file" hidden onChange={handleFileChange} accept=".csv" />
          </Button>
          {selectedFile && (
            <Chip label={selectedFile.name} onDelete={() => setSelectedFile(null)} sx={{ mt: 2 }} />
          )}
        </Box>

        {/* Step 2: Configuration (enabled after file upload) */}
        <FormControl fullWidth sx={{ mb: 3 }} disabled={isFormDisabled}>
          <InputLabel>Dataset Type</InputLabel>
          <Select
            variant="outlined"
            value={dataset}
            label="Dataset Type"
            onChange={(e) => setDataset(e.target.value)}
          >
            <MenuItem value="Heart Disease">Heart Disease</MenuItem>
            <MenuItem value="Diabetes">Diabetes</MenuItem>
          </Select>
        </FormControl>

        <TextField
          label="Number of Rows to Generate"
          type="number"
          variant="outlined"
          value={rowCount}
          onChange={(e) => setRowCount(parseInt(e.target.value, 10))}
          fullWidth
          sx={{ mb: 3 }}
          disabled={isFormDisabled}
        />
        <Box sx={{ mt: 3, textAlign: 'center' }}>
          <Button 
            variant="contained" 
            color="primary" 
            size="large" 
            onClick={handleGenerateClick}
            disabled={isFormDisabled}
          >
            Generate Tabular Data
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};