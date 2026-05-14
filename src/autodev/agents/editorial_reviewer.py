"""EditorialReviewer — pure-Python prose and structure quality checks.

No LLM required.  All checks are heuristic / rule-based and deterministic.

Checks performed
----------------
Prose layer:
  * typos       — tiny built-in stoplist of common English typos
  * terminology — flags noun variants when the same concept is spelled differently
  * passive     — heuristic: >30% sentences contain 'was/were/been + past-participle'
  * long-sentence — sentences >40 words → MINOR

Structure layer:
  * missing-h1   — no H1 heading in document → MAJOR
  * heading-skip — H1 followed by H3+ without H2 → MAJOR
  * broken-link  — [x](path) where *path* doesn't exist on disk → MAJOR
  * toc-mismatch — TOC links that don't match actual headings → MINOR
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schemas import EditorialFinding, EditorialReport, Severity, SeverityFinding

# ---------------------------------------------------------------------------
# Common English typo stoplist (word → correction)
# ---------------------------------------------------------------------------
_TYPOS: dict[str, str] = {
    "recieve": "receive",
    "occured": "occurred",
    "seperate": "separate",
    "definately": "definitely",
    "occurance": "occurrence",
    "accomodate": "accommodate",
    "sucessful": "successful",
    "successfull": "successful",
    "teh": "the",
    "thier": "their",
    "wierd": "weird",
    "beleive": "believe",
    "aquire": "acquire",
    "adress": "address",
    "begining": "beginning",
    "calender": "calendar",
    "collegue": "colleague",
    "commited": "committed",
    "enviroment": "environment",
    "existance": "existence",
    "fourty": "forty",
    "grammer": "grammar",
    "harrass": "harass",
    "independant": "independent",
    "judgement": "judgment",
    "knowlege": "knowledge",
    "liason": "liaison",
    "maintenence": "maintenance",
    "millenium": "millennium",
    "neccessary": "necessary",
    "occassion": "occasion",
    "perseverence": "perseverance",
    "privelege": "privilege",
    "questionaire": "questionnaire",
    "reccomend": "recommend",
    "relavant": "relevant",
    "relevent": "relevant",
    "rythm": "rhythm",
    "schedual": "schedule",
    "sieze": "seize",
    "supercede": "supersede",
    "tendancy": "tendency",
    "untill": "until",
    "visability": "visibility",
    "writting": "writing",
}

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------
_PASSIVE_RE = re.compile(
    r"\b(was|were|been)\s+(\w+ed|built|done|given|known|made|seen|set|shown|told|taken|written)\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

_TOC_LINK_RE = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")


def _severity_finding(
    severity: Severity,
    check: str,
    title: str,
    detail: str = "",
    line: int | None = None,
    snippet: str = "",
) -> SeverityFinding:
    return SeverityFinding(
        severity=severity,
        category="editorial",
        title=title,
        detail=detail,
        line=line,
        source_agent="EditorialReviewer",
    )


class EditorialReviewer:
    """Heuristic prose and structure reviewer for Markdown documents."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review_prose(self, text: str) -> list[EditorialFinding]:
        """Run all prose-layer checks and return findings."""
        findings: list[EditorialFinding] = []
        findings.extend(self._check_typos(text))
        findings.extend(self._check_terminology(text))
        findings.extend(self._check_passive(text))
        findings.extend(self._check_long_sentences(text))
        return findings

    def review_structure(
        self, text: str, file_path: str | None = None
    ) -> list[EditorialFinding]:
        """Run all structure-layer checks and return findings."""
        findings: list[EditorialFinding] = []
        findings.extend(self._check_missing_h1(text))
        findings.extend(self._check_heading_skip(text))
        findings.extend(self._check_broken_links(text, file_path=file_path))
        findings.extend(self._check_toc_mismatch(text))
        return findings

    def review_doc(
        self, text: str, file_path: str | None = None
    ) -> EditorialReport:
        """Run all checks and return a combined EditorialReport."""
        prose = self.review_prose(text)
        structure = self.review_structure(text, file_path=file_path)

        blocker = sum(
            1
            for f in (prose + structure)
            if f.severity_finding and f.severity_finding.severity == Severity.BLOCKER
        )
        major = sum(
            1
            for f in (prose + structure)
            if f.severity_finding and f.severity_finding.severity == Severity.MAJOR
        )
        minor = sum(
            1
            for f in (prose + structure)
            if f.severity_finding and f.severity_finding.severity == Severity.MINOR
        )

        return EditorialReport(
            file_path=file_path,
            prose_findings=prose,
            structure_findings=structure,
            blocker_count=blocker,
            major_count=major,
            minor_count=minor,
            passable=(blocker == 0 and major == 0),
        )

    # ------------------------------------------------------------------
    # Prose checks
    # ------------------------------------------------------------------

    def _check_typos(self, text: str) -> list[EditorialFinding]:
        findings: list[EditorialFinding] = []
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            words = re.findall(r"\b\w+\b", line.lower())
            for word in words:
                if word in _TYPOS:
                    sf = _severity_finding(
                        Severity.MINOR,
                        "typo",
                        f"Possible typo: '{word}' → '{_TYPOS[word]}'",
                        detail=f"Line {lineno}: {line.strip()[:80]}",
                        line=lineno,
                    )
                    findings.append(
                        EditorialFinding(
                            layer="prose",
                            check="typo",
                            line=lineno,
                            snippet=line.strip()[:80],
                            severity_finding=sf,
                        )
                    )
        return findings

    def _check_terminology(self, text: str) -> list[EditorialFinding]:
        """Flag repeated nouns that appear in multiple spelling variants."""
        findings: list[EditorialFinding] = []
        # Extract all multi-char words (lower-cased)
        word_re = re.compile(r"\b([a-zA-Z]{4,})\b")
        all_words: list[str] = word_re.findall(text)
        freq: dict[str, int] = {}
        for w in all_words:
            freq[w.lower()] = freq.get(w.lower(), 0) + 1

        # Simple heuristic: look for pairs where one word is the other + 's' / 'es'
        # or one is a common variant (e.g., "colour"/"color", "behaviour"/"behavior")
        _variants: dict[str, str] = {
            "colour": "color",
            "behaviour": "behavior",
            "honour": "honor",
            "centre": "center",
            "licence": "license",
            "grey": "gray",
        }
        flagged: set[str] = set()
        for variant, canonical in _variants.items():
            if variant in freq and canonical in freq and variant not in flagged:
                flagged.add(variant)
                sf = _severity_finding(
                    Severity.MINOR,
                    "terminology",
                    f"Inconsistent terminology: '{variant}' and '{canonical}' both appear",
                    detail="Use one spelling consistently throughout the document.",
                )
                findings.append(
                    EditorialFinding(
                        layer="prose",
                        check="terminology",
                        snippet=f"'{variant}' vs '{canonical}'",
                        severity_finding=sf,
                    )
                )
        return findings

    def _check_passive(self, text: str) -> list[EditorialFinding]:
        """Flag documents where >30% of sentences use passive voice."""
        sentences = _SENTENCE_SPLIT_RE.split(text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return []

        passive_count = sum(1 for s in sentences if _PASSIVE_RE.search(s))
        ratio = passive_count / len(sentences)

        if ratio > 0.30:
            sf = _severity_finding(
                Severity.MINOR,
                "passive",
                f"Excessive passive voice: {passive_count}/{len(sentences)} sentences "
                f"({ratio:.0%})",
                detail="Consider rewriting passive constructions in active voice.",
            )
            return [
                EditorialFinding(
                    layer="prose",
                    check="passive",
                    snippet=f"{passive_count}/{len(sentences)} sentences passive",
                    severity_finding=sf,
                )
            ]
        return []

    def _check_long_sentences(self, text: str) -> list[EditorialFinding]:
        """Flag sentences >40 words as MINOR."""
        findings: list[EditorialFinding] = []
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            # Split on sentence boundaries within each line
            for sentence in _SENTENCE_SPLIT_RE.split(line):
                words = sentence.split()
                if len(words) > 40:
                    sf = _severity_finding(
                        Severity.MINOR,
                        "long-sentence",
                        f"Sentence exceeds 40 words ({len(words)} words)",
                        detail=sentence[:100],
                        line=lineno,
                    )
                    findings.append(
                        EditorialFinding(
                            layer="prose",
                            check="long-sentence",
                            line=lineno,
                            snippet=sentence[:80],
                            severity_finding=sf,
                        )
                    )
        return findings

    # ------------------------------------------------------------------
    # Structure checks
    # ------------------------------------------------------------------

    def _check_missing_h1(self, text: str) -> list[EditorialFinding]:
        """Return MAJOR finding when no H1 heading is present."""
        headings = _HEADING_RE.findall(text)
        h1_present = any(len(hashes) == 1 for hashes, _ in headings)
        if not h1_present:
            sf = _severity_finding(
                Severity.MAJOR,
                "missing-h1",
                "Document has no H1 heading",
                detail="Every document should begin with exactly one H1 (#) heading.",
            )
            return [
                EditorialFinding(
                    layer="structure",
                    check="missing-h1",
                    severity_finding=sf,
                )
            ]
        return []

    def _check_heading_skip(self, text: str) -> list[EditorialFinding]:
        """Return MAJOR finding when heading levels are skipped (e.g. H1 → H3)."""
        findings: list[EditorialFinding] = []
        _HEADING_RE.finditer(text)
        text.splitlines()

        level_seq: list[tuple[int, int]] = []  # (level, lineno)
        for m in _HEADING_RE.finditer(text):
            level = len(m.group(1))
            # Compute line number
            lineno = text[: m.start()].count("\n") + 1
            level_seq.append((level, lineno))

        for i in range(1, len(level_seq)):
            prev_level, _ = level_seq[i - 1]
            curr_level, curr_line = level_seq[i]
            if curr_level > prev_level + 1:
                sf = _severity_finding(
                    Severity.MAJOR,
                    "heading-skip",
                    f"Heading level skip: H{prev_level} → H{curr_level} at line {curr_line}",
                    detail="Heading levels must not be skipped (e.g. H1 → H3 without H2).",
                    line=curr_line,
                )
                findings.append(
                    EditorialFinding(
                        layer="structure",
                        check="heading-skip",
                        line=curr_line,
                        severity_finding=sf,
                    )
                )
        return findings

    def _check_broken_links(
        self, text: str, file_path: str | None = None
    ) -> list[EditorialFinding]:
        """Return MAJOR finding for each [x](path) where path doesn't exist on disk.

        HTTP/HTTPS links and anchor-only links (#...) are skipped.
        """
        findings: list[EditorialFinding] = []
        base_dir: Path | None = None
        if file_path:
            base_dir = Path(file_path).parent

        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for m in _LINK_RE.finditer(line):
                link_text = m.group(1)
                target = m.group(2)
                # Skip HTTP links and pure anchor links
                if target.startswith(("http://", "https://", "#")):
                    continue
                # Strip anchor from path-with-anchor
                path_part = target.split("#")[0]
                if not path_part:
                    continue

                exists = False
                if base_dir is not None:
                    candidate = base_dir / path_part
                    exists = candidate.exists()
                else:
                    # No base dir → check relative to cwd
                    exists = Path(path_part).exists()

                if not exists:
                    sf = _severity_finding(
                        Severity.MAJOR,
                        "broken-link",
                        f"Broken link: [{link_text}]({target})",
                        detail=f"Path '{path_part}' not found on disk.",
                        line=lineno,
                    )
                    findings.append(
                        EditorialFinding(
                            layer="structure",
                            check="broken-link",
                            line=lineno,
                            snippet=m.group(0)[:80],
                            severity_finding=sf,
                        )
                    )
        return findings

    def _check_toc_mismatch(self, text: str) -> list[EditorialFinding]:
        """Return MINOR findings for TOC entries that don't match any actual heading.

        TOC entries are detected as `[text](#anchor)` links.
        """
        findings: list[EditorialFinding] = []

        # Build set of actual heading anchors (GitHub-style: lower, spaces→hyphens)
        def _to_anchor(heading_text: str) -> str:
            anchor = heading_text.lower()
            anchor = re.sub(r"[^\w\s-]", "", anchor)
            anchor = re.sub(r"\s+", "-", anchor.strip())
            return anchor

        headings = _HEADING_RE.findall(text)
        actual_anchors = {_to_anchor(title) for _, title in headings}

        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for m in _TOC_LINK_RE.finditer(line):
                toc_anchor = m.group(2).lower()
                if toc_anchor not in actual_anchors:
                    sf = _severity_finding(
                        Severity.MINOR,
                        "toc-mismatch",
                        f"TOC entry '#{toc_anchor}' has no matching heading",
                        detail="Update the TOC to match the current heading structure.",
                        line=lineno,
                    )
                    findings.append(
                        EditorialFinding(
                            layer="structure",
                            check="toc-mismatch",
                            line=lineno,
                            snippet=m.group(0)[:80],
                            severity_finding=sf,
                        )
                    )
        return findings
