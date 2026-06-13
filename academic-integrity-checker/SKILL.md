---
name: academic-integrity-checker
description: Pre-submission academic integrity review for manuscripts, theses, grant-derived papers, figures, references, author declarations, ethics statements, data/code availability, AI-use disclosure, plagiarism/overlap risk, fabricated or falsified data warning signs, image-duplication risk, paper-mill signals, citation manipulation, authorship problems, conflicts of interest, duplicate publication, retracted/compromised literature checks, and online reference verification. Use when Codex is asked to check a scholarly manuscript before journal submission, verify whether references really exist, detect fabricated citations, or identify clearly inappropriate citation-context mismatches.
---

# Academic Integrity Checker

## Core Workflow

Treat this skill as a prevention and warning tool, not as a misconduct adjudicator. Flag risks, missing disclosures, and inconsistencies that authors can fix before submission.

1. Identify the manuscript type and field: clinical/human subjects, animal research, lab biology with images, computational/data science, qualitative/social science, review/meta-analysis, or general scholarly work.
2. Run `scripts/check_manuscript.py` on the manuscript text and any available figure/image folder.
3. For final pre-submission checks, add `--online-references` to verify each reference against Crossref/DOI.org and, when available, OpenAlex metadata.
4. Read `references/misconduct_taxonomy.md` when interpreting categories, severity, and remediation.
5. Read `references/reference_audit.md` when interpreting online reference verification and citation-context findings.
6. Read `references/validated_cases.json` when examples, validation cases, or known proven patterns are needed.
7. Produce a concise report with: critical blockers, high-risk warnings, medium/low hygiene issues, evidence snippets from the manuscript, reference-verification status, and concrete fixes.

## Quick Start

```bash
python academic-integrity-checker/scripts/check_manuscript.py path/to/manuscript.md --figures path/to/figures --format markdown
```

Online reference audit:

```bash
python academic-integrity-checker/scripts/check_manuscript.py path/to/manuscript.docx --online-references --max-references 120 --format markdown
```

Supported manuscript inputs: `.txt`, `.md`, `.docx`. PDF extraction is intentionally omitted unless a project already has a reliable PDF text extractor installed; ask for a text/docx export when needed.

Useful options:

- `--cases academic-integrity-checker/references/validated_cases.json` checks references against bundled proven-case titles/DOIs.
- `--compare-corpus path/to/prior-work-folder` checks local overlap against the author's previous manuscripts or known source files.
- `--online-references` verifies parsed references through Crossref and DOI.org; OpenAlex is used opportunistically when reachable.
- `--max-references N` caps online checks for long bibliographies.
- `--format json` returns machine-readable findings for downstream tools.

## Report Standards

Classify findings by actionability:

- `critical`: submission should pause until fixed, e.g. missing human-subject ethics approval for human data, undisclosed clinical trial registration, exact duplicate figure files labeled as different experiments, citation to a known retracted case as valid evidence, or absent raw-data support for central claims.
- `high`: likely journal/institutional concern, e.g. no data availability statement, missing conflict/funding disclosure, image-adjustment language absent in image-heavy papers, unexplained sample-size changes, inconsistent numbers across abstract/results/tables.
- `medium`: fix before submission, e.g. incomplete author contribution statement, weak AI-use disclosure, unsupported novelty claims, reference metadata anomalies.
- `low`: hygiene, clarity, and auditability improvements.

Never state that a person committed misconduct. Use language like "risk", "inconsistency", "missing disclosure", "requires author verification", or "resembles a proven pattern".

## Checks To Perform

Always check:

- Research-misconduct core: fabrication, falsification, and plagiarism.
- Publication ethics: duplicate/overlapping publication, salami slicing, self-plagiarism without citation, redundant submission, misleading citation practices, paper-mill/template signals.
- Authorship and accountability: contribution statement, corresponding-author accountability, acknowledgments, ghost/gift authorship warning signs.
- Disclosures: funding, conflicts of interest, AI assistance, data/code/material availability.
- Ethics compliance: IRB/ethics approval, consent, clinical trial registration, animal welfare approval, field/site permissions as applicable.
- Evidence traceability: claims tied to methods, data, figures, supplementary files, protocols, and statistical reporting.
- Images/figures: exact duplicate files, reused figure labels, missing microscopy/blot adjustment disclosure, composite-image/splicing disclosure.
- References: placeholder citations, fake-looking DOIs, retracted/proven-problem works in the bundled case set, excessive self-citation, coercive/citation-cartel patterns if bibliographic data is available.
- Online reference audit: DOI existence, strict Crossref title match for no-DOI references, title/year/first-author/venue mismatch, unresolved or fabricated-looking references, and obvious citation-context mismatch such as citing a non-review paper as a review, citing a non-dataset paper as a dataset source, or using a reference whose title/abstract has almost no topical overlap with the local citation sentence.

## Remediation Guidance

For every serious finding, propose a fix authors can do before submission:

- Add or correct ethics approval/consent/trial registration statements.
- Add data/code/material availability with repository, accession, restriction reason, and contact route.
- Reconcile inconsistent sample sizes, denominators, p-values, figure labels, and group names.
- Replace manipulated/composite figures with raw-supported versions, document legitimate global adjustments, and mark splices.
- Add citations for reused text, methods, data, images, or prior conference/preprint versions.
- Verify each author meets the target journal's authorship criteria and approve the final manuscript.
- Disclose AI assistance according to journal policy and confirm authors verified all AI-assisted content.
- Remove fabricated placeholders, unverifiable citations, unsupported novelty/causality claims, and references to retracted work unless explicitly discussed as retracted.
- For unresolved references, verify DOI/title manually in Crossref, publisher pages, PubMed, arXiv, IEEE/ACM/Springer/Elsevier, or Google Scholar; replace fabricated or unverifiable references before submission.
- For citation-context mismatches, either cite a more appropriate source or rewrite the sentence so the cited work actually supports the claim.

## Limits

Static checking cannot prove originality, data authenticity, consent validity, or intent. Online bibliographic checks depend on third-party metadata quality and network availability; an unresolved reference is a warning for manual verification, not proof that the reference is fake. When risk remains high, recommend institutional research-integrity review, journal policy consultation, raw-data audit, image-forensics review, plagiarism software, or statistical review.
