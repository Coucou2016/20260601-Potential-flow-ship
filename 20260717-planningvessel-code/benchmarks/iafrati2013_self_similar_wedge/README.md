# Iafrati 2013 self-similar wedge benchmark

This directory contains two independent, post-solve references from Alessandro
Iafrati, *A fully nonlinear iterative solution method for self-similar potential
flows with a free boundary* (2013, arXiv:1212.6699v2).

`table1_pressure_peak.csv` is a manual transcription of the Zhao--Faltinsen
pressure-peak columns in Table 1.  It checks the maximum dimensionless pressure
coefficient and its vertical similarity coordinate for 10, 20 and 30 degrees.

`iafrati2013_20deg_outer_free_surface.csv` is extracted directly from vector
operations in the source figure `cfg_5-20_arxiv1212.6699v2.pdf`.  It is an
independent cross-audit for the 20-degree outer free surface and is not a
replacement selected to improve the Zhao--Faltinsen acceptance score.

Neither reference is read by the self-similar solver or its optimizer.  The
directory manifest records the full article PDF, arXiv source archive, vector
figure, CSV hashes, quantity definitions and extraction policy.
