# Legacy column-median digitization

This directory preserves the superseded Sun 2007 Figure 2.6 digitization.

The legacy algorithm thresholded blue pixels inside frozen regions of interest
and reduced every image column to the median row.  Where the upward spray branch
and lower outer free-surface branch both occur in one column, that median can lie
between the two observed pixel clusters and therefore does not represent either
physical branch.

The files are retained only for audit and impact comparison.  They must not be
used as the current Gate 2 acceptance reference.

Frozen CSV SHA-256:
`27501c457dbe61fa2ad9c2bea020ed66780cb7ab6214f3c3f7317d045eb8c994`.
