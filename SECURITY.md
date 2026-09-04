# Security and private data

- Store credentials only in ignored config.local.json (or config.*.local.json).
  The public config.example.json intentionally contains empty API keys.
- Never attach local configuration, state databases, raw LLM responses, generated
  reports or feedback to public issues. They can contain private research context.
- Custom projects under references/projects are ignored except the blank template.
  Review custom Profile content before committing changes: Profiles are public source files.
- Build public files with scripts/build_release.py. It exports committed, allowlisted
  files only and rejects likely credentials rather than trying to hide them after upload.
  The detector is a safety check, not a guarantee against every possible secret format.
- If a credential was exposed, revoke/rotate it at its provider. Deleting a current
  file does not remove a secret from Git history.
- For a suspected vulnerability, use GitHub private vulnerability reporting if it
  is available on the repository. Do not publish credentials or exploit data in issues.

This beta uses external bibliographic, embedding, translation and model services.
When enabled, those services receive paper metadata and (for Judge) selected
research/project descriptions. Use only services appropriate for your data.
