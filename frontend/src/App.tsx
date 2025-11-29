import React, { useState } from 'react';
import {
  Container,
  CssBaseline,
  Box,
  Tabs,
  Tab,
  Typography,
  CircularProgress,
  Snackbar,
  Alert,
  AppBar,
  Toolbar,
  ThemeProvider,
  createTheme
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import axios from 'axios';

// Import all of our components
import { TabularGenerator } from './components/TabularGenerator';
import { ImageGenerator } from './components/ImageGenerator';
import { GenomicGenerator } from './components/GenomicGenerator';
import { TimeSeriesGenerator } from './components/TimeSeriesGenerator';

// --- Theme Definition ---
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1976d2' },
    background: { default: '#f4f6f8', paper: '#ffffff' },
  },
  typography: {
    fontFamily: 'Inter, sans-serif',
    h3: { fontWeight: 700 },
  },
  components: {
    MuiTab: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 500, fontSize: '1rem' },
      },
    },
  },
});

// Helper function to trigger a file download
const triggerDownload = (url: string, filename: string) => {
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};


function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState<{ open: boolean, message: string, severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  // Use the environment variable, or fallback to localhost for development
  // This ensures it works both locally and on the deployed site
  const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000';

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleGenerate = async (config: any, file?: File) => {
    setLoading(true);
    const endpoint = `${apiUrl}/api/generate/${config.type}`;

    const formData = new FormData();
    formData.append('config', JSON.stringify(config));
    if (file) {
      formData.append('sourceFile', file);
    }

    try {
      const response = await axios.post(endpoint, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.status === 'success') {
        setAlert({ open: true, message: 'Generation successful! Downloading...', severity: 'success' });
        const filename = response.data.fileUrl.split('/').pop();
        triggerDownload(response.data.fileUrl, filename);
      } else {
        throw new Error(response.data.message || 'An unknown backend error occurred.');
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.details || error.message || 'Failed to connect to backend.';
      setAlert({ open: true, message: `Error: ${errorMessage}`, severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleCloseAlert = () => setAlert({ ...alert, open: false });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <AppBar position="static">
          <Toolbar>
            <ScienceIcon sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Synthetic Medical Data Generation Tool
            </Typography>
            {loading && <CircularProgress color="inherit" size={24} />}
          </Toolbar>
        </AppBar>

        {/* The maxWidth="lg" prop has been removed to make the container full-width */}
        <Container component="main" sx={{ mt: 4, mb: 4 }}>
          <Box sx={{ width: '100%', borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Tabs value={activeTab} onChange={handleTabChange} centered variant="scrollable" scrollButtons="auto">
              <Tab label="Tabular Data" />
              <Tab label="Medical Imaging" />
              <Tab label="Genomic Data" />
              <Tab label="Time-Series Data" />
            </Tabs>
          </Box>
          
          <Box sx={{ mt: 3 }}>
            {activeTab === 0 && <TabularGenerator onGenerate={handleGenerate} />}
            {activeTab === 1 && <ImageGenerator onGenerate={handleGenerate} />}
            {activeTab === 2 && <GenomicGenerator onGenerate={handleGenerate} />}
            {activeTab === 3 && <TimeSeriesGenerator onGenerate={handleGenerate} />}
          </Box>
        </Container>

        <Snackbar open={alert.open} autoHideDuration={6000} onClose={handleCloseAlert}>
          <Alert onClose={handleCloseAlert} severity={alert.severity} sx={{ width: '100%' }}>
            {alert.message}
          </Alert>
        </Snackbar>
      </Box>
    </ThemeProvider>
  );
}

export default App;