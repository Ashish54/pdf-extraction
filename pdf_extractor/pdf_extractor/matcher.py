"""Matching config section titles against outline Sections.

Matching is normalized exact match (NFKD, casefold, whitespace-collapsed) with
match-all semantics: one config entry keeps every Section with that title.
Over-keeping is recoverable; under-keeping is silent data loss.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from .outline import Section

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")

#: Normalized titles treated as the printed table of contents.
PRINTED_TOC_TITLES = frozenset({"contents", "table of contents"})


def normalize(title: str) -> str:
    """Canonical form for title comparison."""
    t = unicodedata.normalize("NFKD", title)
    t = t.casefold()
    return _WS_RE.sub(" ", t).strip()


@dataclass
class MatchResult:
    # config entry (original spelling) -> every Section it matched
    matched: dict[str, list[Section]] = field(default_factory=dict)
    unmatched: list[str] = field(default_factory=list)

    @property
    def sections(self) -> list[Section]:
        """Unique matched Sections, in document order."""
        seen: set[int] = set()
        out: list[Section] = []
        for hits in self.matched.values():
            for s in hits:
                if id(s) not in seen:
                    seen.add(id(s))
                    out.append(s)
        out.sort(key=lambda s: (s.start_page, s.level))
        return out


def match_sections(config_titles: list[str], sections: list[Section]) -> MatchResult:
    by_norm: dict[str, list[Section]] = {}
    for s in sections:
        by_norm.setdefault(normalize(s.title), []).append(s)

    result = MatchResult()
    for entry in config_titles:
        hits = by_norm.get(normalize(entry), [])
        if not hits:
            result.unmatched.append(entry)
            logger.warning("Config section %r matched no outline entry", entry)
            continue
        result.matched[entry] = hits
        if len(hits) > 1:
            logger.warning(
                "Config section %r matched %d outline entries (starting pages %s); "
                "all kept (match-all)",
                entry,
                len(hits),
                ", ".join(str(s.start_page + 1) for s in hits),
            )
    return result


def find_printed_toc(sections: list[Section]) -> list[Section]:
    """Sections whose title marks them as the printed table of contents."""
    return [s for s in sections if normalize(s.title) in PRINTED_TOC_TITLES]
