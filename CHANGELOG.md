# Changelog

## v0.1.0-beta

First public beta based on the MIT-licensed frontier-tracker-LIS implementation.

- Three independent Research Profiles, optional Project Context, shared SQLite state.
- CrossRef discovery, Semantic Scholar discovery, OpenAlex enrichment.
- Keyword recall, optional embeddings, structured LLM research judgments and translation.
- Strict Judge field/type validation, response retry archives, content-aware checkpoints.
- Personalized bilingual HTML, Excel, feedback App, Markdown notes and preview.
- Cross-provider excluded journals (PLOS ONE excluded by default).
- Discoverable repository Skill, secret-free release exporter and Windows/Linux CI.

### Known beta limits

- No independent arXiv provider; Semantic Scholar may incidentally include preprints.
- Feedback is stored, not automatically used to train weights or rewrite Profiles.
- Local sentence-transformers/BGE model backend is optional and not live-validated here.
- Metadata coverage and abstracts depend on providers. LLM claims require verification.
- Tests use deterministic service doubles; live provider availability is not guaranteed.
- No background scheduler, full-text analysis, or multi-user web backend.
- HTML/Excel/App show all candidates; capacity limits apply to notes/reading preview.
