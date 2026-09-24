# Literature-reading boundary and calibration record

## What was completed

The 12+5+5 calibration set in `calibration-matrix.csv` contains **22 distinct
complete papers**: 12 ACM TODS papers, five influential learned-index papers,
and five adjacent papers on dynamic maintenance, robustness, or empirical
evaluation.  For every row, the matrix now records the exact full-text source,
the version reviewed, page count, review date, the paper's problem framing,
argument structure, evaluation breadth, artifact strength, narrative sequence,
and the concrete pattern adopted or rejected here.

The complete-paper review covered the title and abstract, every numbered main
section, evaluation or worked examples, conclusion, references, and appendices
included in the reviewed version.  It was a **writing and novelty calibration**:
it does not turn this project into an independent peer review, a systematic
literature review, or proof that no uncatalogued work subsumes the result.
Publisher PDFs, proceedings PDFs, or complete author manuscripts were used as
listed; no scholarly PDF is redistributed in the artifact.

## Calibration set

### Same venue: ACM Transactions on Database Systems (12)

1. Bayer and Unterauer, *Prefix B-Trees* (1977), ACM published PDF.
2. Benedikt et al., *Rewriting the Infinite Chase for Guarded TGDs* (2024),
   author-deposited complete manuscript corresponding to the TODS article.
3. Park et al., *Accurate Sampling-Based Cardinality Estimation for Complex
   Graph Queries* (2024), author-hosted complete manuscript corresponding to
   the TODS article.
4. Bender and Hu, *An Adaptive Packed-Memory Array* (2007), ACM published PDF.
5. Graf and Lemire, *Succinct Range Filters* (2020), complete author preprint
   corresponding to the TODS article.
6. Binna et al., *Height Optimized Tries* (2022), author-hosted TODS PDF.
7. Psallidas et al., *Supporting Better Insights of Data Science Pipelines with
   Fine-grained Provenance* (2024), ACM published PDF.
8. Bertossi et al., *Database Repairing with Soft Functional Dependencies*
   (2024), ACM published PDF.
9. Crooks et al., *Ad Hoc Transactions through the Looking Glass* (2024), ACM
   published PDF.
10. Graefe, *A Survey of B-Tree Locking Techniques* (2010), ACM published PDF.
11. Livshits et al., *Computing Optimal Repairs for Functional Dependencies*
    (2020), complete author preprint corresponding to the TODS article.
12. Beame et al., *Exact Model Counting of Query Expressions: Limitations of
    Propositional Methods* (2017), ACM published PDF, DOI 10.1145/2984632.

### Influential learned-index papers (5)

13. Kraska et al., *The Case for Learned Index Structures* (SIGMOD 2018),
    complete author preprint including appendices.
14. Ferragina and Vinciguerra, *The PGM-index* (PVLDB 2020), PVLDB published
    PDF.
15. Ding et al., *ALEX* (SIGMOD 2020), author-hosted final manuscript.
16. Galakatos et al., *FITing-Tree* (SIGMOD 2019), ACM published PDF.
17. Marcus et al., *Benchmarking Learned Indexes* (PVLDB 2020), PVLDB
    published PDF.

### Adjacent recent papers (5)

18. Wongkham et al., *Are Updatable Learned Indexes Ready?* (PVLDB 2022),
    PVLDB published PDF.
19. Yang et al., *Algorithmic Complexity Attacks on Dynamic Learned Indexes*
    (PVLDB 2024), PVLDB published PDF.
20. Gæde et al., *A Dynamic Piecewise-Linear Geometric Index with Worst-Case
    Guarantees* (ESA 2025), LIPIcs published paper; the arXiv full version was
    also checked for appendices.
21. Luo et al., *Understanding Robustness Issues of Updatable Learned Indexes:
    Experiments and Analysis* (PACMMOD 2025), ACM published PDF.
22. Sun et al., *Learned Index: A Comprehensive Experimental Evaluation*
    (PVLDB 2023), PVLDB published PDF.

## Technical-claim boundary

Full-paper calibration is broader than the passages used to support technical
comparisons.  The following comparisons were checked at the relevant definitions,
algorithms, theorem statements, update mechanisms, and experimental sections:

- Kraska et al. bound correction over the currently stored keys and discuss
  update strategies; this is not a guarantee for every future set under a fixed
  predictor.
- PGM, ALEX, FITing-Tree, and the dynamic geometric index maintain or rebuild
  models, components, or layouts; the present result instead certifies a frozen
  compact-rank predictor over a declared final-set family and one declared replay.
- The updatable-index readiness, attack, robustness, and broad benchmark papers
  measure operational behavior.  They motivate conservative non-claims here;
  finite proof checks and exact envelopes are not presented as production
  throughput evidence.
- The same-venue papers were used primarily to calibrate TODS-length exposition:
  formal scope before theorem stacks, explicit protocol semantics, negative
  results retained in the abstract and conclusion, and evidence separated from
  proof.

Additional bibliography items were screened or read only to the extent needed
for the claims they support.  They are not silently counted among the 22
complete-paper calibration records.  The manuscript therefore makes a narrow
closest-work delta, not a universal priority claim.
