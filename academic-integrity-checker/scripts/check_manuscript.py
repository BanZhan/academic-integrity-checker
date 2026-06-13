#!/usr/bin/env python3
"""Pre-submission academic integrity checker.

This script is intentionally conservative. It finds missing disclosures,
inconsistencies, and static warning signs; it does not adjudicate misconduct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


CHECK_PATTERNS = [
    {
        "id": "missing_data_availability",
        "severity": "high",
        "category": "data availability",
        "required_absent": [
            r"data availability",
            r"availability of data",
            r"raw data",
            r"repository",
            r"accession",
            r"deposited",
        ],
        "message": "No specific data availability statement was detected.",
        "remediation": "Add a data availability statement with repository/accession, restrictions, and contact route.",
    },
    {
        "id": "missing_conflict_statement",
        "severity": "high",
        "category": "disclosures",
        "required_absent": [
            r"conflict[s]? of interest",
            r"competing interest",
            r"financial interest",
            r"declaration of interest",
        ],
        "message": "No conflict/competing-interest disclosure was detected.",
        "remediation": "Add a conflict-of-interest statement, even if it states that none exist.",
    },
    {
        "id": "missing_funding_statement",
        "severity": "medium",
        "category": "disclosures",
        "required_absent": [
            r"funding",
            r"grant",
            r"supported by",
            r"funder",
            r"award number",
        ],
        "message": "No funding statement or grant support language was detected.",
        "remediation": "Add funding sources, grant numbers, and funder role; state no funding if applicable.",
    },
    {
        "id": "missing_author_contributions",
        "severity": "medium",
        "category": "authorship",
        "required_absent": [
            r"author contributions?",
            r"contributorship",
            r"CRediT",
            r"conceptualization",
            r"methodology",
        ],
        "message": "No author contribution statement was detected.",
        "remediation": "Add a contribution statement and confirm all authors approved the final manuscript.",
    },
    {
        "id": "missing_ai_disclosure",
        "severity": "medium",
        "category": "AI disclosure",
        "required_absent": [
            r"artificial intelligence",
            r"generative AI",
            r"large language model",
            r"ChatGPT",
            r"AI-assisted",
        ],
        "message": "No AI-use disclosure was detected.",
        "remediation": "If AI tools were used, disclose tool, purpose, and author verification; otherwise follow the target journal policy.",
    },
]


CONDITIONAL_PATTERNS = [
    {
        "id": "human_subjects_without_ethics",
        "severity": "critical",
        "category": "human subjects",
        "trigger": [
            r"\bpatients?\b",
            r"\bparticipants?\b",
            r"\bvolunteers?\b",
            r"\bhuman subjects?\b",
            r"\bclinical\b",
            r"\bmedical records?\b",
            r"\bsurvey\b",
            r"\binterviews?\b",
        ],
        "required": [
            r"\bIRB\b",
            r"ethics committee",
            r"institutional review board",
            r"informed consent",
            r"ethics approval",
            r"approved by",
        ],
        "message": "Human-subject language appears, but ethics approval/consent language is missing or weak.",
        "remediation": "Add ethics approval identifier, waiver if applicable, consent statement, and participant protection details.",
    },
    {
        "id": "clinical_trial_without_registration",
        "severity": "critical",
        "category": "clinical trial",
        "trigger": [
            r"clinical trial",
            r"randomi[sz]ed",
            r"placebo",
            r"intervention",
            r"trial participants",
        ],
        "required": [
            r"ClinicalTrials\.gov",
            r"\bNCT\d{8}\b",
            r"trial registration",
            r"registered",
            r"ISRCTN",
            r"registry",
        ],
        "message": "Clinical-trial language appears, but trial registration was not detected.",
        "remediation": "Add registry name, registration number, date, protocol link, and explain any retrospective registration.",
    },
    {
        "id": "animal_study_without_approval",
        "severity": "critical",
        "category": "animal research",
        "trigger": [
            r"\bmice\b",
            r"\bmouse\b",
            r"\brats?\b",
            r"\banimal model\b",
            r"\bzebrafish\b",
            r"\bporcine\b",
        ],
        "required": [
            r"IACUC",
            r"animal ethics",
            r"animal care",
            r"ARRIVE",
            r"approved by",
            r"welfare",
        ],
        "message": "Animal-research language appears, but animal ethics/welfare approval was not detected.",
        "remediation": "Add animal ethics approval, welfare standard, ARRIVE compliance where relevant, and protocol identifier.",
    },
    {
        "id": "image_heavy_without_image_policy",
        "severity": "high",
        "category": "image integrity",
        "trigger": [
            r"western blot",
            r"immunoblot",
            r"microscopy",
            r"micrograph",
            r"confocal",
            r"gel electrophoresis",
            r"fluorescence",
        ],
        "required": [
            r"uncropped",
            r"raw image",
            r"image adjustment",
            r"brightness",
            r"contrast",
            r"splic",
            r"source data",
        ],
        "message": "Image-heavy experimental language appears, but raw/source image or adjustment disclosure was not detected.",
        "remediation": "Provide uncropped/source images, disclose legitimate global adjustments, and mark/document any splicing.",
    },
]


SUSPICIOUS_REFERENCE_PATTERNS = [
    r"doi:\s*10\.xxxx",
    r"\bDOI\s*:\s*TBD\b",
    r"\bref(?:erence)? needed\b",
    r"\bcitation needed\b",
    r"\bplaceholder\b",
    r"\bINSERT\b",
]


OVERCLAIM_PATTERNS = [
    r"\bfirst ever\b",
    r"\bno previous studies\b",
    r"\bprove[s]?\b",
    r"\bdefinitive(?:ly)?\b",
    r"\bwithout any limitations\b",
    r"\bperfect(?:ly)?\b",
]


REFERENCE_HEADING_RE = re.compile(r"^\s*(references|bibliography|works cited)\s*:?\s*$", re.IGNORECASE)
SECTION_HEADING_RE = re.compile(r"^\s*[A-Z][A-Za-z /&-]{2,60}\s*$")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
AUTHOR_CONNECTOR_RE = re.compile(r"\b(and|et\s+al\.?)\b", re.IGNORECASE)

SUPPORT_KEYWORDS = {
    "review": {"review", "survey", "overview", "meta-analysis", "systematic"},
    "dataset": {"dataset", "database", "benchmark", "corpus", "repository", "data set"},
    "clinical": {"clinical", "patient", "diagnosis", "trial", "medical", "tumor", "cancer"},
    "method": {"method", "model", "algorithm", "classification", "segmentation", "prediction"},
}


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".rst"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        return read_docx(path)
    raise SystemExit(f"Unsupported manuscript type: {path.suffix}. Use .txt, .md, or .docx.")


def read_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
    except KeyError as exc:
        raise SystemExit("Invalid .docx: missing word/document.xml") from exc
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for para in root.findall(".//w:p", ns):
        texts = [node.text or "" for node in para.findall(".//w:t", ns)]
        if texts:
            paragraphs.append("".join(texts))
    return "\n".join(paragraphs)


def read_paragraphs(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".rst"}:
        return [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as zf:
                xml = zf.read("word/document.xml")
        except KeyError as exc:
            raise SystemExit("Invalid .docx: missing word/document.xml") from exc
        root = ElementTree.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for para in root.findall(".//w:p", ns):
            texts = [node.text or "" for node in para.findall(".//w:t", ns)]
            text = "".join(texts).strip()
            if text:
                paragraphs.append(text)
        return paragraphs
    return [read_text(path)]


def has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def snippets(text: str, patterns: list[str], max_items: int = 3) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    found = []
    for line in lines:
        if has_any(line, patterns):
            found.append(line[:240])
        if len(found) >= max_items:
            break
    return found


def add_finding(findings: list[dict[str, Any]], **kwargs: Any) -> None:
    finding = {
        "id": kwargs.pop("id"),
        "severity": kwargs.pop("severity"),
        "category": kwargs.pop("category"),
        "message": kwargs.pop("message"),
        "evidence": kwargs.pop("evidence", []),
        "remediation": kwargs.pop("remediation", ""),
    }
    finding.update(kwargs)
    findings.append(finding)


def check_required_sections(text: str, findings: list[dict[str, Any]]) -> None:
    for check in CHECK_PATTERNS:
        if not has_any(text, check["required_absent"]):
            add_finding(findings, **check, evidence=[])
            findings[-1].pop("required_absent", None)

    for check in CONDITIONAL_PATTERNS:
        trigger_hit = has_any(text, check["trigger"])
        required_hit = has_any(text, check["required"])
        if trigger_hit and not required_hit:
            add_finding(
                findings,
                id=check["id"],
                severity=check["severity"],
                category=check["category"],
                message=check["message"],
                evidence=snippets(text, check["trigger"]),
                remediation=check["remediation"],
            )


def check_reference_hygiene(text: str, findings: list[dict[str, Any]]) -> None:
    bad_snippets = snippets(text, SUSPICIOUS_REFERENCE_PATTERNS, max_items=5)
    if bad_snippets:
        add_finding(
            findings,
            id="suspicious_reference_placeholders",
            severity="high",
            category="references",
            message="Reference placeholders or fake-looking DOI markers were detected.",
            evidence=bad_snippets,
            remediation="Resolve every placeholder; verify DOI, title, authors, venue, and that each citation supports the claim.",
        )

    overclaims = snippets(text, OVERCLAIM_PATTERNS, max_items=5)
    if overclaims:
        add_finding(
            findings,
            id="unsupported_absolute_claims",
            severity="medium",
            category="claims",
            message="Absolute novelty/causality claims were detected and should be checked against the evidence.",
            evidence=overclaims,
            remediation="Qualify claims or add strong supporting evidence and citations.",
        )


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value: str) -> str:
    value = re.sub(r"https?://\S+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bdoi\s*:?\s*10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[^a-z0-9 ]+", " ", value.lower())
    stop = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "the",
        "to",
        "with",
        "using",
        "based",
        "by",
        "from",
    }
    return " ".join(word for word in value.split() if word not in stop)


def token_set(value: str) -> set[str]:
    return set(normalize_title(value).split())


def title_similarity(left: str, right: str) -> float:
    left_words = token_set(left)
    right_words = token_set(right)
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / max(1, len(left_words | right_words))


def title_coverage(query: str, candidate: str) -> float:
    query_words = token_set(query)
    candidate_words = token_set(candidate)
    if not query_words:
        return 0.0
    return len(query_words & candidate_words) / len(query_words)


def extract_references(paragraphs: list[str]) -> list[dict[str, Any]]:
    start = None
    for i, para in enumerate(paragraphs):
        if REFERENCE_HEADING_RE.match(para):
            start = i + 1
            break
    if start is None:
        return []

    refs: list[str] = []
    current = ""
    for para in paragraphs[start:]:
        if SECTION_HEADING_RE.match(para) and not DOI_RE.search(para) and len(refs) > 3:
            break
        if re.match(r"^\s*(\[\d+\]|\d+\.|\d+\))\s+", para):
            if current:
                refs.append(current.strip())
            current = para
        elif current:
            current += " " + para
        elif para:
            refs.append(para)
    if current:
        refs.append(current.strip())

    parsed = []
    for index, raw in enumerate(refs, start=1):
        marker = re.match(r"^\s*(?:\[(\d+)\]|(\d+)[.)])\s+", raw)
        ref_id = int(next(group for group in marker.groups() if group)) if marker else index
        cleaned = re.sub(r"^\s*(?:\[\d+\]|\d+[.)])\s+", "", raw).strip()
        parsed.append(
            {
                "id": ref_id,
                "raw": cleaned,
                "doi": extract_doi(cleaned),
                "year": extract_year(cleaned),
                "title_guess": guess_reference_title(cleaned),
                "first_author": guess_first_author(cleaned),
                "container_guess": guess_container(cleaned),
            }
        )
    return parsed


def extract_doi(reference: str) -> str | None:
    match = DOI_RE.search(reference)
    if not match:
        return None
    return match.group(0).rstrip(".,;)")


def extract_year(reference: str) -> str | None:
    matches = YEAR_RE.findall(reference)
    full = re.findall(r"\b(?:19|20)\d{2}\b", reference)
    return full[-1] if full else None


def guess_first_author(reference: str) -> str | None:
    cleaned = re.sub(r"^\s*(?:\[\d+\]|\d+[.)])\s+", "", reference).strip()
    match = re.match(r"([A-Z][A-Za-z'`-]+)", cleaned)
    return match.group(1) if match else None


def guess_reference_title(reference: str) -> str:
    quoted = re.search(r"[\"“](.+?)[\"”]", reference)
    if quoted:
        return normalize_space(quoted.group(1))
    pre_year = re.split(r"\b(?:19|20)\d{2}\b", reference, maxsplit=1)[0]
    comma_parts = [part.strip() for part in pre_year.split(",") if part.strip()]
    for part in reversed(comma_parts):
        words = part.split()
        if 3 <= len(words) <= 30 and not AUTHOR_CONNECTOR_RE.search(part):
            return normalize_space(part)
    parts = [part.strip() for part in re.split(r"\.\s+", reference) if part.strip()]
    if len(parts) >= 2 and re.search(r"\b[A-Z][A-Za-z'`-]+(?:\s+[A-Z]\b|,)", parts[0]):
        if 2 <= len(parts[1].split()) <= 30 and not DOI_RE.search(parts[1]) and not URL_RE.search(parts[1]):
            return normalize_space(parts[1])
    candidates = []
    for part in parts:
        if DOI_RE.search(part) or URL_RE.search(part):
            continue
        if YEAR_RE.search(part) and len(part.split()) < 6:
            continue
        if len(part.split()) >= 2:
            candidates.append(part)
    if not candidates:
        return normalize_space(reference[:180])
    return normalize_space(max(candidates, key=lambda item: len(item.split())))


def guess_container(reference: str) -> str | None:
    without_urls = URL_RE.sub("", reference)
    without_doi = DOI_RE.sub("", without_urls)
    patterns = [
        r"\.\s*([^.,]+?)\s*,\s*vol\.",
        r"\.\s*([^.,]+?)\s*,\s*\[online\]",
        r"\.\s*([^.,]+?)\s*\.\s*doi",
        r"Proceedings of\s+([^.,]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, without_doi, flags=re.IGNORECASE)
        if match:
            value = normalize_space(match.group(1))
            if value and len(value.split()) <= 12:
                return value
    return None


def http_json(url: str, timeout: int = 15, user_agent: str | None = None) -> dict[str, Any] | None:
    headers = {
        "Accept": "application/json",
        "User-Agent": user_agent or "academic-integrity-checker/0.1 (mailto:anonymous@example.com)",
    }
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status >= 400:
                return None
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def crossref_by_doi(doi: str, user_agent: str | None) -> dict[str, Any] | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
    data = http_json(url, user_agent=user_agent)
    if not data:
        return None
    return data.get("message")


def doi_org_metadata(doi: str, user_agent: str | None) -> dict[str, Any] | None:
    url = "https://doi.org/" + urllib.parse.quote(doi, safe="/")
    return http_json(url, user_agent=user_agent)


def crossref_search(reference: dict[str, Any], user_agent: str | None, rows: int = 3) -> list[dict[str, Any]]:
    query = reference.get("title_guess") or reference.get("raw") or ""
    params = urllib.parse.urlencode({"query.title": query, "rows": rows})
    data = http_json("https://api.crossref.org/works?" + params, user_agent=user_agent)
    if not data:
        return []
    return data.get("message", {}).get("items", []) or []


def item_title(item: dict[str, Any]) -> str:
    titles = item.get("title") or []
    return normalize_space(titles[0]) if titles else ""


def item_year(item: dict[str, Any]) -> str | None:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = item.get(key, {}).get("date-parts")
        if parts and parts[0]:
            return str(parts[0][0])
    return None


def item_first_author(item: dict[str, Any]) -> str | None:
    authors = item.get("author") or []
    if not authors:
        return None
    return authors[0].get("family") or authors[0].get("name")


def item_container(item: dict[str, Any]) -> str | None:
    titles = item.get("container-title") or []
    return normalize_space(titles[0]) if titles else None


def same_year(reference_year: str | None, metadata_year: str | None) -> bool:
    if not reference_year or not metadata_year:
        return True
    return reference_year == metadata_year


def compatible_first_author(reference_author: str | None, metadata_author: str | None) -> bool:
    if not reference_author or not metadata_author:
        return True
    left = reference_author.lower()
    right = metadata_author.lower()
    return left in right or right in left


def compatible_container(reference_container: str | None, metadata_container: str | None) -> bool:
    if not reference_container or not metadata_container:
        return True
    score = title_similarity(reference_container, metadata_container)
    coverage = max(title_coverage(reference_container, metadata_container), title_coverage(metadata_container, reference_container))
    return score >= 0.55 or coverage >= 0.75


def strict_reference_match(reference: dict[str, Any], item: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    ref_title = reference.get("title_guess") or reference.get("raw") or ""
    online_title = item_title(item)
    score = title_similarity(ref_title, online_title)
    coverage = title_coverage(ref_title, online_title)
    if score < 0.82 and coverage < 0.92:
        reasons.append(f"title not exact enough ({score:.0%} similarity, {coverage:.0%} coverage)")
    if not same_year(reference.get("year"), item_year(item)):
        reasons.append(f"year differs: manuscript={reference.get('year')} online={item_year(item)}")
    if not compatible_first_author(reference.get("first_author"), item_first_author(item)):
        reasons.append(f"first author differs: manuscript={reference.get('first_author')} online={item_first_author(item)}")
    if not compatible_container(reference.get("container_guess"), item_container(item)):
        reasons.append(f"venue differs: manuscript={reference.get('container_guess')} online={item_container(item)}")
    return not reasons, reasons


def metadata_summary(item: dict[str, Any]) -> str:
    title = item_title(item) or "untitled"
    doi = item.get("DOI", "")
    year = item_year(item) or "n.d."
    source = (item.get("container-title") or [""])[0]
    bits = [title, year]
    if source:
        bits.append(source)
    if doi:
        bits.append("doi:" + doi)
    return " | ".join(bits)


def reference_contexts(paragraphs: list[str], ref_id: int) -> list[str]:
    patterns = [
        re.compile(rf"\[{ref_id}\]"),
        re.compile(rf"\b{ref_id}\b"),
    ]
    contexts = []
    for para in paragraphs:
        if REFERENCE_HEADING_RE.match(para):
            break
        if any(pattern.search(para) for pattern in patterns):
            contexts.append(para[:500])
    return contexts[:5]


def openalex_by_doi(doi: str, user_agent: str | None) -> dict[str, Any] | None:
    url = "https://api.openalex.org/works/doi:" + urllib.parse.quote("https://doi.org/" + doi, safe="")
    return http_json(url, user_agent=user_agent)


def context_mismatch(reference: dict[str, Any], metadata: dict[str, Any] | None, contexts: list[str]) -> list[str]:
    if not contexts:
        return []
    text = " ".join(contexts).lower()
    title = (item_title(metadata or {}) or reference.get("title_guess") or reference.get("raw") or "").lower()
    problems = []
    for label, words in SUPPORT_KEYWORDS.items():
        if any(word in text for word in words):
            title_hit = any(word in title for word in words)
            if not title_hit:
                problems.append(f"context discusses {label}, but verified title has weak topical overlap")
    if metadata and title_similarity(" ".join(contexts), item_title(metadata)) < 0.03 and len(" ".join(contexts).split()) > 30:
        problems.append("citation sentence has very low lexical overlap with verified title")
    return problems[:2]


def check_online_references(
    paragraphs: list[str],
    references: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    max_references: int,
    sleep_seconds: float,
    user_agent: str | None,
) -> None:
    if not references:
        add_finding(
            findings,
            id="no_reference_section_detected",
            severity="medium",
            category="references",
            message="No reference section could be parsed for online verification.",
            evidence=[],
            remediation="Ensure references are under a clear 'References' or 'Bibliography' heading and use numbered entries.",
        )
        return

    checked = references[:max_references]
    unresolved = []
    mismatches = []
    context_warnings = []
    verified_count = 0
    doi_count = 0

    for reference in checked:
        metadata = None
        source = "Crossref"
        if reference.get("doi"):
            doi_count += 1
            metadata = crossref_by_doi(reference["doi"], user_agent)
            if not metadata:
                doi_meta = doi_org_metadata(reference["doi"], user_agent)
                if doi_meta:
                    metadata = {
                        "DOI": reference["doi"],
                        "title": [doi_meta.get("title", "")] if doi_meta.get("title") else [],
                        "author": doi_meta.get("author") or [],
                        "issued": doi_meta.get("issued") or doi_meta.get("published"),
                        "container-title": doi_meta.get("container-title") or [],
                    }
                    source = "DOI.org"
            if not metadata:
                unresolved.append(f"[{reference['id']}] DOI not resolved: {reference['doi']} | {reference['title_guess']}")
                time.sleep(sleep_seconds)
                continue
        else:
            candidates = crossref_search(reference, user_agent, rows=10)
            best = None
            best_score = 0.0
            best_reasons: list[str] = []
            for item in candidates:
                exact, reasons = strict_reference_match(reference, item)
                score = title_similarity(reference.get("title_guess") or reference["raw"], item_title(item))
                coverage = title_coverage(reference.get("title_guess") or reference["raw"], item_title(item))
                rank_score = max(score, coverage)
                if exact:
                    best = item
                    best_score = rank_score
                    best_reasons = []
                    break
                if rank_score > best_score:
                    best = item
                    best_score = rank_score
                    best_reasons = reasons
            if best and not best_reasons:
                metadata = best
            else:
                hint = f"; closest: {metadata_summary(best)}; reasons: {'; '.join(best_reasons)}" if best else ""
                unresolved.append(f"[{reference['id']}] No exact Crossref match: {reference['title_guess']}{hint}")
                time.sleep(sleep_seconds)
                continue

        verified_count += 1
        title_score = title_similarity(reference.get("title_guess") or reference["raw"], item_title(metadata))
        if title_score < 0.35:
            mismatches.append(
                f"[{reference['id']}] low title match ({title_score:.0%}): manuscript='{reference['title_guess']}' | {source}='{metadata_summary(metadata)}'"
            )
        if reference.get("year") and item_year(metadata) and reference["year"] != item_year(metadata):
            mismatches.append(
                f"[{reference['id']}] year mismatch: manuscript={reference['year']} | {source}={item_year(metadata)} | {metadata_summary(metadata)}"
            )
        first_author = reference.get("first_author")
        crossref_author = item_first_author(metadata)
        if first_author and crossref_author and first_author.lower() not in crossref_author.lower() and crossref_author.lower() not in first_author.lower():
            if title_score < 0.7:
                mismatches.append(
                    f"[{reference['id']}] first-author mismatch: manuscript={first_author} | {source}={crossref_author} | {metadata_summary(metadata)}"
                )

        contexts = reference_contexts(paragraphs, reference["id"])
        context_problems = context_mismatch(reference, metadata, contexts)
        for problem in context_problems:
            context_warnings.append(f"[{reference['id']}] {problem}: {contexts[0][:220] if contexts else reference['raw'][:220]}")

        if reference.get("doi"):
            openalex_by_doi(reference["doi"], user_agent)
        time.sleep(sleep_seconds)

    if unresolved:
        add_finding(
            findings,
            id="online_unresolved_references",
            severity="high",
            category="references",
            message="Some references could not be confidently verified online.",
            evidence=unresolved[:20],
            remediation="Manually verify these entries in Crossref, publisher pages, PubMed, arXiv, IEEE/ACM, Springer/Elsevier, or Google Scholar; replace unverifiable references.",
            checked_references=len(checked),
        )
    if mismatches:
        add_finding(
            findings,
            id="online_reference_metadata_mismatch",
            severity="high",
            category="references",
            message="Online metadata does not clearly match some manuscript references.",
            evidence=mismatches[:20],
            remediation="Correct DOI, title, year, author order, venue, and page/article numbers against publisher/Crossref metadata.",
            checked_references=len(checked),
        )
    if context_warnings:
        add_finding(
            findings,
            id="possible_inappropriate_citation_context",
            severity="medium",
            category="references",
            message="Some citations may not clearly support the local claim based on title/context overlap.",
            evidence=context_warnings[:20],
            remediation="Open the cited paper and verify that it supports the sentence; cite a more appropriate source or rewrite the claim.",
            checked_references=len(checked),
        )

    add_finding(
        findings,
        id="online_reference_audit_summary",
        severity="low",
        category="references",
        message=f"Online reference audit checked {len(checked)} reference(s): {verified_count} verified, {len(unresolved)} unresolved, {doi_count} with DOI.",
        evidence=[],
        remediation="Treat unresolved or mismatched entries as manual-verification tasks before submission.",
    )


def extract_numbers(text: str) -> list[tuple[str, str]]:
    patterns = [
        (r"\bn\s*=\s*(\d+)\b", "n"),
        (r"\bN\s*=\s*(\d+)\b", "N"),
        (r"\bsample size\s*(?:of|=|:)?\s*(\d+)\b", "sample size"),
        (r"\b(\d+)\s+(?:patients|participants|samples|mice|rats|cells)\b", "count"),
    ]
    out = []
    for pattern, label in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            out.append((label, match.group(0)))
    return out


def check_number_consistency(text: str, findings: list[dict[str, Any]]) -> None:
    counts = extract_numbers(text)
    normalized = [value.lower().replace(" ", "") for _, value in counts]
    distinct = sorted(set(normalized))
    if len(distinct) >= 8:
        add_finding(
            findings,
            id="many_distinct_sample_counts",
            severity="medium",
            category="data consistency",
            message="Many distinct sample-size/count statements were detected; verify denominators across abstract, methods, figures, and tables.",
            evidence=[value for _, value in counts[:10]],
            remediation="Create a sample-size reconciliation table and ensure exclusions/missing data are explained.",
        )

    p_values = re.findall(r"\bp\s*[<=>]\s*0?\.\d+", text, flags=re.IGNORECASE)
    if len(p_values) >= 20:
        top = [f"{item} ({count})" for item, count in Counter(p_values).most_common(5)]
        add_finding(
            findings,
            id="dense_p_value_reporting",
            severity="low",
            category="statistics",
            message="Dense p-value reporting detected; confirm multiplicity correction, exact test names, and effect sizes.",
            evidence=top,
            remediation="Report test, assumptions, effect size, confidence interval, multiplicity correction, and analysis plan.",
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_figures(figures: Path | None, findings: list[dict[str, Any]]) -> None:
    if not figures:
        return
    if not figures.exists():
        add_finding(
            findings,
            id="figure_path_missing",
            severity="medium",
            category="image integrity",
            message=f"Figure path does not exist: {figures}",
            evidence=[],
            remediation="Provide the correct figure/source-image directory for duplicate and traceability checks.",
        )
        return

    image_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
    files = [path for path in figures.rglob("*") if path.is_file() and path.suffix.lower() in image_exts]
    if not files:
        add_finding(
            findings,
            id="no_figure_files_found",
            severity="low",
            category="image integrity",
            message="No image files were found in the provided figure directory.",
            evidence=[],
            remediation="Provide final figures and source images if the manuscript relies on visual evidence.",
        )
        return

    by_hash: dict[str, list[str]] = defaultdict(list)
    for path in files:
        by_hash[sha256_file(path)].append(str(path))
    duplicates = [paths for paths in by_hash.values() if len(paths) > 1]
    if duplicates:
        add_finding(
            findings,
            id="exact_duplicate_image_files",
            severity="critical",
            category="image integrity",
            message="Exact duplicate image files were found. This may be legitimate only if reuse is clearly labeled and disclosed.",
            evidence=[" | ".join(group) for group in duplicates[:5]],
            remediation="Verify each duplicate against source data; relabel, replace, or disclose legitimate reuse.",
        )

    stems = Counter(re.sub(r"[_\-\s]?(copy|final|new|edited|adjusted)\d*$", "", p.stem, flags=re.IGNORECASE).lower() for p in files)
    ambiguous = [name for name, count in stems.items() if count > 1]
    if ambiguous:
        add_finding(
            findings,
            id="ambiguous_figure_versions",
            severity="medium",
            category="image integrity",
            message="Multiple similarly named figure versions were found.",
            evidence=ambiguous[:10],
            remediation="Keep a clear source-to-final figure map and remove stale/ambiguous versions before submission.",
        )


def word_shingles(text: str, size: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < size:
        return set()
    return {tuple(words[i : i + size]) for i in range(len(words) - size + 1)}


def check_local_overlap(text: str, corpus: Path | None, findings: list[dict[str, Any]]) -> None:
    if not corpus:
        return
    if not corpus.exists():
        add_finding(
            findings,
            id="compare_corpus_missing",
            severity="medium",
            category="plagiarism/overlap",
            message=f"Comparison corpus path does not exist: {corpus}",
            evidence=[],
            remediation="Provide the correct folder of prior manuscripts/source material.",
        )
        return
    target = word_shingles(text)
    if not target:
        return
    overlaps = []
    for path in corpus.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".markdown", ".docx"}:
            try:
                other = word_shingles(read_text(path))
            except Exception:
                continue
            if not other:
                continue
            score = len(target & other) / max(1, len(target | other))
            if score >= 0.08:
                overlaps.append((score, str(path)))
    if overlaps:
        overlaps.sort(reverse=True)
        add_finding(
            findings,
            id="local_text_overlap",
            severity="high",
            category="plagiarism/overlap",
            message="Text overlap with local corpus was detected.",
            evidence=[f"{score:.1%} shingle overlap: {path}" for score, path in overlaps[:10]],
            remediation="Cite and quote/paraphrase prior work appropriately; disclose overlap with preprints, theses, conference papers, or prior articles.",
        )


def load_cases(path: Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def check_known_cases(text: str, cases: list[dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    hits = []
    for case in cases:
        work = case.get("affected_work", {})
        probes = [work.get("doi"), work.get("title")]
        for probe in [item for item in probes if item]:
            if probe.lower() in text.lower():
                hits.append(f"{case['id']}: {probe}")
    if hits:
        add_finding(
            findings,
            id="known_proven_case_cited",
            severity="critical",
            category="references",
            message="The manuscript appears to cite or mention a bundled proven misconduct/retraction-risk case.",
            evidence=hits,
            remediation="Do not cite retracted/compromised work as valid evidence. If discussed, explicitly state its status and reason.",
        )


def risk_score(findings: list[dict[str, Any]]) -> int:
    weights = {"critical": 30, "high": 15, "medium": 7, "low": 2}
    return min(100, sum(weights.get(item["severity"], 0) for item in findings))


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    manuscript = Path(args.manuscript)
    text = read_text(manuscript)
    paragraphs = read_paragraphs(manuscript)
    findings: list[dict[str, Any]] = []
    check_required_sections(text, findings)
    check_reference_hygiene(text, findings)
    check_number_consistency(text, findings)
    check_figures(Path(args.figures) if args.figures else None, findings)
    check_local_overlap(text, Path(args.compare_corpus) if args.compare_corpus else None, findings)
    check_known_cases(text, load_cases(Path(args.cases)) if args.cases else [], findings)
    if args.online_references:
        check_online_references(
            paragraphs,
            extract_references(paragraphs),
            findings,
            args.max_references,
            args.reference_sleep,
            args.user_agent,
        )
    findings.sort(key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["id"]))
    words = re.findall(r"\S+", text)
    return {
        "manuscript": str(manuscript),
        "word_count": len(words),
        "risk_score": risk_score(findings),
        "finding_count": len(findings),
        "findings": findings,
        "limits": "Static and online screening flags risks and omissions; it cannot prove misconduct, originality, consent validity, data authenticity, or whether every cited claim is substantively supported.",
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Academic Integrity Pre-Submission Report",
        "",
        f"- Manuscript: `{report['manuscript']}`",
        f"- Word count: {report['word_count']}",
        f"- Risk score: {report['risk_score']}/100",
        f"- Findings: {report['finding_count']}",
        "",
        "## Findings",
    ]
    if not report["findings"]:
        lines.append("")
        lines.append("No static integrity warnings were detected. This is not a guarantee of compliance.")
    for item in report["findings"]:
        lines.extend(
            [
                "",
                f"### [{item['severity'].upper()}] {item['category']} - {item['id']}",
                "",
                item["message"],
            ]
        )
        if item.get("evidence"):
            lines.append("")
            lines.append("Evidence:")
            for evidence in item["evidence"]:
                lines.append(f"- {evidence}")
        if item.get("remediation"):
            lines.append("")
            lines.append(f"Fix: {item['remediation']}")
    lines.extend(["", "## Limits", "", report["limits"]])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pre-submission academic integrity checks.")
    parser.add_argument("manuscript", help="Manuscript file: .txt, .md, or .docx")
    parser.add_argument("--figures", help="Optional directory containing final/source figure images")
    parser.add_argument("--compare-corpus", help="Optional folder of local prior work/source files")
    parser.add_argument("--cases", help="Optional validated_cases.json file")
    parser.add_argument("--online-references", action="store_true", help="Verify parsed references using Crossref/DOI.org/OpenAlex metadata")
    parser.add_argument("--max-references", type=int, default=120, help="Maximum references to check online")
    parser.add_argument("--reference-sleep", type=float, default=0.15, help="Seconds to sleep between reference API requests")
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Optional User-Agent with contact email for scholarly APIs, e.g. 'academic-integrity-checker/0.1 (mailto:name@example.com)'",
    )
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    report = build_report(args)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(markdown(report))
    return 0 if not any(item["severity"] == "critical" for item in report["findings"]) else 2


if __name__ == "__main__":
    sys.exit(main())
