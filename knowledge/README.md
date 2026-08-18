# Knowledge base for the agent

Drop **.txt**, **.md**, or **.pdf** files here (resume, bio, FAQs, project notes).

Their contents are loaded into the agent's context at startup. The agent uses this information to answer questions and will not invent details that aren't here.

**Audit trail:** on each startup the backend hashes each file, versions changes, and appends events to `knowledge/.audit/events.jsonl`. Previous snapshots are kept under `knowledge/.audit/versions/`. Metadata only — no secrets in logs.

Provenance per file (in `/dev`): **Git added** (first commit), **Git last commit**, **File modified** (filesystem mtime).

**Not loaded as persona content:** this README only (`README.md` is skipped).

Current files:
- `Daniel_David_Resume.pdf` — latest resume/CV
- `LinkedIn_Bio.md` — LinkedIn About/Bio (synced region) plus local career preferences
- `Protfolio - Daniel David.pdf` — portfolio

Examples to add:
- `faq.md` — frequently asked questions and answers
- `projects.md` — project write-ups
