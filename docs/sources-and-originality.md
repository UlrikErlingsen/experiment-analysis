# Sources and originality

## Independent scope

ExperimentSignal is an original software implementation of public statistical ideas for randomized experiments. Its product structure, interface, prose, code, decision statuses, synthetic example, graphics, and evidence schema were created for this project.

ExperimentSignal is independently designed and written from the published statistical literature below. It does not reproduce lecture slides, speaker notes, cases, exercises, assessment questions, figures, tables, diagrams, or any institution-specific teaching material, and no such file is shipped, quoted, transformed, or required at runtime. General topics encountered in education—experiment design and analysis—only define the problem domain.

The fictional 2×2 demonstration is generated from a documented random seed. Its organization, treatment labels, variables, assignments, outcomes, and effect pattern do not represent real data or a classroom case.

## Public methodological foundation

The implementation is grounded in independently published literature:

- Neyman's repeated-randomization foundation for treatment-effect estimation;
- Rubin's potential-outcomes framing;
- Welch's unequal-variance comparison;
- MacKinnon and White's HC3 covariance;
- Holm's sequential familywise multiplicity control;
- Lin's agnostic regression adjustment for randomized experiments;
- the ASA statement's limits on p-value interpretation;
- Lakens's emphasis on effect sizes and cumulative interpretation.

These methods belong to the scientific record; citing them acknowledges intellectual provenance. ExperimentSignal's license applies to this project's particular code and documentation, not to ownership of statistical concepts.

## Language and safeguards

The app intentionally avoids claiming that:

- randomization can be inferred from balanced data;
- a p-value is the probability a hypothesis is true;
- statistical significance establishes importance;
- regression adjustment fixes confounding or post-treatment selection;
- factorial omnibus tests replace declared estimands;
- a generic sample-size convention is appropriate for every design;
- unsupported clustered, repeated, adaptive, or non-Gaussian designs can be analyzed as ordinary independent means.

Contributions should preserve this independence. Use public sources, original explanations, and synthetic/openly licensed test fixtures. Do not submit proprietary teaching content or identifiable participant data.

