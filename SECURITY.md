# Security policy

## Supported version

Security fixes target the latest release on the default branch.

## Reporting

Please report a suspected vulnerability privately through GitHub's security-advisory feature when the repository is published. Never include confidential experiment data in a public issue.

## Data-handling notes

ExperimentSignal accepts CSV, XLSX, and JSON tables up to 50 MB and applies row/column limits. It does not execute workbook macros. Exported text that could be interpreted as a spreadsheet formula is neutralized. Aggregate evidence exports omit row-level experimental records.

These controls do not turn ExperimentSignal into a hardened multi-tenant service. A hosted deployment should add authentication, TLS, authorization, rate limiting, secure headers, isolated storage, dependency monitoring, logging appropriate to the data classification, and a documented deletion policy.

