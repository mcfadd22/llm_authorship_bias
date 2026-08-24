# llm_authors

Study on how LLM judges ascribe folk-psychological states (intentionality,
blame, ability-vs-diligence) to buggy code based on claimed authorship
(self, other named model, generic AI, human developer, or no label),
crossed with whether the bug defeats or is orthogonal to the code's stated
purpose, bug type, and severity.

See [`docs/design.md`](docs/design.md) for the full design doc: manipulated
factors, prompt template, question battery, response schema, and the
confirmatory/exploratory pre-registration split.

## Structure

- `docs/` — design docs, pre-registration notes
- `config/` — machine-readable vignette parameters (see `docs/config-schema.md`)
- `scripts/` — elicitation and data-generation scripts
- `analysis/` — analysis code (WCB clustering, Holm correction, NLP coding pass)
- `data/` — raw/intermediate data (gitignored except placeholder)
