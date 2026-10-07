import { createTheme } from "@mui/material";
export const theme = createTheme({
  palette: {
    primary: { main: "#175c62" },
    secondary: { main: "#405774" },
    success: { main: "#25633e" },
    warning: { main: "#835500" },
    error: { main: "#a32c35" },
    info: { main: "#315f87" },
    background: { default: "#f4f6f8", paper: "#ffffff" },
    text: { primary: "#20313e", secondary: "#536573" },
    divider: "#dce3e8",
  },
  typography: {
    fontFamily: "Inter, Segoe UI, Arial, sans-serif",
    h4: { fontSize: "1.85rem", fontWeight: 650 },
    h5: { fontSize: "1.35rem", fontWeight: 650 },
    h6: { fontSize: "1.1rem", fontWeight: 650 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiCard: { defaultProps: { variant: "outlined" } },
    MuiTextField: { defaultProps: { size: "small" } },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiTableCell: {
      styleOverrides: { head: { backgroundColor: "#f4f6f8", fontWeight: 650 } },
    },
    MuiCssBaseline: {
      styleOverrides: {
        "*:focus-visible": {
          outline: "3px solid #315f87",
          outlineOffset: "3px",
        },
      },
    },
  },
});
