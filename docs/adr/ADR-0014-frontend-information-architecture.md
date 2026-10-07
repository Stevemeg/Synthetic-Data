# ADR-0014: route-based governed workspace

Status: Accepted. Phase 5.

## Decision

Retain React, TypeScript and Material UI. Add React Router with stable project/dataset/run/evaluation routes, a persistent responsive shell, project-scoped subnavigation and lazy feature modules. Typed API access remains centralized in Axios. Local form state and a cancellable polling/resource hook are sufficient; no Redux or frontend backend rewrite is introduced.

Workspace inventories and project counts use bounded backend queries and grouped aggregates rather than per-card requests. Accessible HTML/CSS bars with numeric tables provide the small fidelity visualization requirement without a charting dependency. Separate evidence views preserve Phase 4 methodology and comparison compatibility checks.

## Consequences

Resources are shareable and refreshable, initial code is split, and complex forms have focused feature boundaries. History routes require a static-host SPA fallback when using a future host; Vite dev/preview provide this locally. Tables scroll at tablet width. The application does not imply authentication through fake users or roles. Browser verification is distinct from DOM/backend verification.
