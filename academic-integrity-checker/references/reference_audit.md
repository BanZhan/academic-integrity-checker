# Online Reference Audit

Use `--online-references` for final pre-submission checks when network access is available.

## What The Script Verifies

- Extract numbered references after a `References`, `Bibliography`, or `Works cited` heading.
- Resolve references with DOI through Crossref.
- Search no-DOI references by title through Crossref.
- Accept an online match only when the title is near-exact and available year, first-author, and venue metadata do not conflict.
- Compare manuscript reference title/year/first author/venue against online metadata.
- Flag unresolved references, low-confidence metadata matches, year/author mismatches, and rough citation-context mismatch.

## How To Interpret Findings

- `online_unresolved_references`: Treat as high-priority manual verification. The checker deliberately prefers unresolved over a loose similar-paper match. It may be a fabricated reference, but it may also be a formatting issue, non-indexed venue, book chapter, preprint, local standard, or metadata gap.
- `online_reference_metadata_mismatch`: Correct the DOI, title, year, authors, journal, and article number against publisher/Crossref metadata.
- `possible_inappropriate_citation_context`: This is heuristic. Open the cited paper and verify the exact sentence. Rewrite the claim or cite a better source if the citation does not support it.
- `online_reference_audit_summary`: Informational count of checked, verified, unresolved, and DOI-bearing references.

## Manual Escalation

For unresolved references, check at least two of: publisher page, Crossref, DOI.org, PubMed, arXiv, IEEE Xplore, ACM Digital Library, SpringerLink, ScienceDirect, Scopus/Web of Science, institutional repository, or Google Scholar.

Do not accuse authors of fabrication solely from an unresolved API check.
