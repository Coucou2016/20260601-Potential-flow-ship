# Aborted diagnostic, not a result

- Status: `ABORTED_DIAGNOSTIC_NOT_A_RESULT`
- Source: `self_similar_wedge_19deg_n160_panelpre4_cfl0125_resume5_v408`
- Requested operation: one 64-mode, root-preserving, curvature-gated trust-region iteration.
- Reason: the finite-difference construction repeatedly performed a full matching-surface search for every perturbed mode. No result artifact was produced after approximately 50 minutes, so the run was interrupted before candidate acceptance or rejection.
- Interpretation: this directory contains no physical or numerical result and must not be used in validation, convergence, or continuation.
- Required remedy: make each perturbation inherit the source matching-surface branch and invoke the global relocation search only when that local build is physically inadmissible.
