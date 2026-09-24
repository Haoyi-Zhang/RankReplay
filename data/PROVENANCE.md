# Exact public numeric input

`wine_numeric.csv` is the unmodified numeric CSV distributed with the installed
scikit-learn Wine loader. Its first row is metadata (178 samples, 13 features and
three class names); subsequent rows contain 13 feature values followed by a
zero-based class index. No package code is run to derive the selected keys.

The underlying dataset is UCI Wine, S. Aeberhard and M. Forina (1992),
DOI 10.24432/C5PC7J, https://archive.ics.uci.edu/dataset/109/wine.
The UCI page was read on 2026-09-14 and states Creative Commons Attribution 4.0.
Scikit-learn documents the loader at
https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_wine.html.
Acquisition: exact copy of the locally supplied public package data. A direct
network download was unavailable; this is not described as a newly downloaded
UCI file. The consumed bytes are included, avoiding dependence on a future
package release or preprocessing change. The package's numeric layout differs
from the original UCI class-first file; the producer of that layout is
scikit-learn, not this project.

Selection is fixed before evaluation: read feature 13 (Proline, zero-based
column 12) using decimal-to-integer conversion, require integral values, sort
and deduplicate. Rows are not filtered using evaluation results or labels. Use
every distinct value. Classes and all other features are ignored. This is a
small public integer-key slice, not a database query/update workload or evidence
of biological, medical or production performance. Generated updates on this
slice remain generated updates.

Attribution: Aeberhard, S., and Forina, M. (1992). Wine [Dataset]. UCI Machine
Learning Repository. https://doi.org/10.24432/C5PC7J. CC BY 4.0:
https://creativecommons.org/licenses/by/4.0/ . No changes to the included CSV;
the selected integer key file is a derived, sorted, deduplicated projection.
