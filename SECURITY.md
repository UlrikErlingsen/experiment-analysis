# Security policy

## Supported version

Security fixes target the latest release on the default branch.

## Reporting

Please report a suspected vulnerability privately through GitHub's security-advisory feature when the repository is published. Never include confidential experiment data in a public issue.

## Data-handling notes

Experiment Signal accepts CSV, XLSX and JSON tables. Run locally it has no built-in size, row or column limit (memory is the limit, and running out of memory is reported plainly). A public demo sets `SIGNAL_PUBLIC=1`, which caps uploads at 50 MB, 250,000 rows (CSV parsing stops one row past the cap), 500 columns and 4,999 permutations; anyone hosting a shared copy should set it. It does not execute workbook macros. Exported text that could be interpreted as a spreadsheet formula is neutralized. Aggregate evidence exports omit row-level experimental records.

These controls do not turn Experiment Signal into a hardened multi-tenant service. A hosted deployment should add authentication, TLS, authorization, rate limiting, secure headers, isolated storage, dependency monitoring, logging appropriate to the data classification, and a documented deletion policy.

