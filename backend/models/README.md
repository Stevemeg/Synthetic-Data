# Model compatibility

Pretrained artifacts stay in `backend/`, the default `MODEL_DIR`; no binaries have
been moved or deleted. `MODEL_DIR/trained/<run_id>/vae.pt` holds new full PyTorch
VAE checkpoints with dimensions, normalization, seed, epochs, and format version.
These learned weights may carry disclosure risk and are not served by HTTP.

The two SDV TVAE pickles and legacy Keras decoder are preserved but are not API
engines. Only trusted local model files may be loaded. Pickle-based artifacts
must never come from HTTP uploads. See `docs/BASELINE_AUDIT.md` for inventory,
hashes, provenance limitations, and checkpoint compatibility checks.
