# Security Policy

## Scope

Security issues include:

- Vulnerabilities in automation scripts or JSON workflows  
- Exposure of private data, credentials, or API keys  
- Flaws enabling unsafe or unintended automated behavior, especially if triggerable remotely or without explicit user consent  

Model output quality or coaching logic disagreements are not security issues.

Keep `.sync_config`, legacy `.sync_config.json` and `.sync_config.saved-*` private. The new name avoids JSON-file selection; copying or syncing the whole data folder still includes credentials.

## Reporting

Use GitHub **Private Vulnerability Reporting**  
(Security tab → "Report a vulnerability").

If unavailable, open a GitHub issue marked `Security` without sensitive details.

## Response

Reports are acknowledged within 7 days.

Confirmed issues will be fixed or mitigated before public disclosure.
