# ADR-0007: Reconstructible training/holdout partitions

Accepted in Phase 3. Use versioned NumPy PCG64 positional permutation with a seed,
floor(n*fraction) holdout, source order retained within partitions, minimum 10
training rows and holdout disabled with warning below 20 source rows. Default
fraction 0.2. Train only the training partition; retain hashes/algorithm/version/
seed/fractions/counts instead of downloadable source partitions. Reconstruct
only after immutable source checksum verification. This enables future held-out
evaluation without implementing Phase 4 and is not a patient-grouped split.
