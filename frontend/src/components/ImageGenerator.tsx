import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField,
  Typography,
  Chip,
  Grid
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import ImageSearchIcon from '@mui/icons-material/ImageSearch';

export const ImageGenerator = ({ onGenerate }: { onGenerate: (config: any, file?: File) => void }) => {
  const [count, setCount] = useState(10);
  const [modality, setModality] = useState('MRI');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleGenerateClick = () => {
    // Ensure count is a valid number before sending
    const finalCount = count > 0 ? count : 1;
    onGenerate({ type: 'imaging', count: finalCount, modality }, selectedFile || undefined);
  };

  return (
    <Card sx={{ mt: 2 }}>
      <CardContent sx={{ p: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 3 }}>
          <ImageSearchIcon sx={{ fontSize: '2.5rem', mr: 1, color: 'primary.main' }} />
          <Typography variant="h4" gutterBottom align="center" sx={{ mb: 0 }}>
            Medical Imaging Generator
          </Typography>
        </Box>

        <Grid container spacing={3} sx={{ alignItems: 'center' }}>
          <Grid item xs={12}>
            <Box sx={{ p: 2, border: '1px dashed grey', borderRadius: 1, textAlign: 'center' }}>
              <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
                Upload Sample Image (Optional)
                <input type="file" hidden accept="image/*" onChange={handleFileChange} />
              </Button>
              {selectedFile && (
                <Chip label={selectedFile.name} onDelete={() => setSelectedFile(null)} sx={{ mt: 2, ml: 2 }} />
              )}
            </Box>
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              label="Number of Images to Generate"
              type="number"
              variant="outlined"
              value={count}
              // Ensure value doesn't drop below 1 visually, handle NaN
              onChange={(e) => {
                 const val = parseInt(e.target.value, 10);
                 setCount(isNaN(val) ? 0 : val);
              }}
              inputProps={{ min: 1 }}
              fullWidth
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Modality</InputLabel>
              <Select variant="outlined" value={modality} label="Modality" onChange={(e) => setModality(e.target.value)}>
                <MenuItem value="MRI">Brain MRI</MenuItem>
                <MenuItem value="X-Ray">Chest X-Ray</MenuItem>
                <MenuItem value="Skin">Skin Lesion</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>

        <Box sx={{ mt: 4, textAlign: 'center' }}>
          <Button variant="contained" color="primary" size="large" onClick={handleGenerateClick} disabled={count < 1}>
            Generate Images
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};