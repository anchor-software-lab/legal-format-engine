"""Firm reference database - 160+ firms with fuzzy matching for normalization."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class FirmRecord:
    """A firm in the reference database."""
    canonical_name: str
    category: str  # "am_law", "appellate", "state_ag", "state_pd", "wisconsin", "legal_aid", "federal"
    rank: Optional[int] = None
    aliases: list[str] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


class FirmDatabase:
    """Reference database of major law firms with fuzzy matching."""

    def __init__(self):
        self._firms: list[FirmRecord] = []
        self._build_database()

    def _build_database(self):
        """Populate the firm database."""
        # Am Law top 50
        am_law = [
            ("Kirkland & Ellis LLP", 1),
            ("Latham & Watkins LLP", 2),
            ("DLA Piper", 3),
            ("Baker McKenzie", 4),
            ("Skadden, Arps, Slate, Meagher & Flom LLP", 5),
            ("Sidley Austin LLP", 6),
            ("Morgan, Lewis & Bockius LLP", 7),
            ("Jones Day", 8),
            ("White & Case LLP", 9),
            ("Hogan Lovells", 10),
            ("Gibson, Dunn & Crutcher LLP", 11),
            ("Greenberg Traurig LLP", 12),
            ("Goodwin Procter LLP", 13),
            ("Davis Polk & Wardwell LLP", 14),
            ("Sullivan & Cromwell LLP", 15),
            ("Simpson Thacher & Bartlett LLP", 16),
            ("Weil, Gotshal & Manges LLP", 17),
            ("Wilson Sonsini Goodrich & Rosati", 18),
            ("Paul, Weiss, Rifkind, Wharton & Garrison LLP", 19),
            ("Cleary Gottlieb Steen & Hamilton LLP", 20),
            ("Norton Rose Fulbright", 21),
            ("Reed Smith LLP", 22),
            ("Morrison & Foerster LLP", 23),
            ("K&L Gates LLP", 24),
            ("Dentons", 25),
            ("Covington & Burling LLP", 26),
            ("Quinn Emanuel Urquhart & Sullivan LLP", 27),
            ("McDermott Will & Emery LLP", 28),
            ("Willkie Farr & Gallagher LLP", 29),
            ("Orrick, Herrington & Sutcliffe LLP", 30),
            ("Arnold & Porter LLP", 31),
            ("Cooley LLP", 32),
            ("Mayer Brown LLP", 33),
            ("Akin Gump Strauss Hauer & Feld LLP", 34),
            ("Ropes & Gray LLP", 35),
            ("Milbank LLP", 36),
            ("Perkins Coie LLP", 37),
            ("Holland & Knight LLP", 38),
            ("Debevoise & Plimpton LLP", 39),
            ("Winston & Strawn LLP", 40),
            ("Proskauer Rose LLP", 41),
            ("O'Melveny & Myers LLP", 42),
            ("Shearman & Sterling LLP", 43),
            ("Baker Botts LLP", 44),
            ("Pillsbury Winthrop Shaw Pittman LLP", 45),
            ("Squire Patton Boggs", 46),
            ("King & Spalding LLP", 47),
            ("Vinson & Elkins LLP", 48),
            ("Paul Hastings LLP", 49),
            ("Dechert LLP", 50),
        ]
        for name, rank in am_law:
            self._firms.append(FirmRecord(canonical_name=name, category="am_law", rank=rank))

        # Appellate specialists
        appellate = [
            "Goldstein & Russell, P.C.",
            "Bancroft PLLC",
            "Kannon Shanmugam (Paul Weiss - Appellate)",
            "Clement & Murphy PLLC",
            "Robbins, Russell, Englert, Orseck, Untereiner & Sauber LLP",
            "Howe & Russell, P.C.",
            "Jenner & Block LLP - Appellate Practice",
            "WilmerHale - Appellate and Supreme Court Litigation",
        ]
        for name in appellate:
            self._firms.append(FirmRecord(canonical_name=name, category="appellate"))

        # Wisconsin-specific
        wisconsin = [
            "Foley & Lardner LLP",
            "Michael Best & Friedrich LLP",
            "Quarles & Brady LLP",
            "Reinhart Boerner Van Deuren S.C.",
            "Godfrey & Kahn S.C.",
            "von Briesen & Roper S.C.",
            "Husch Blackwell LLP",
            "Boardman & Clark LLP",
            "Axley Brynelson LLP",
            "DeWitt LLP",
        ]
        for name in wisconsin:
            self._firms.append(FirmRecord(canonical_name=name, category="wisconsin"))

        # Federal
        federal = [
            "United States Department of Justice",
            "Office of the Solicitor General",
            "Federal Public Defender",
        ]
        for name in federal:
            self._firms.append(FirmRecord(canonical_name=name, category="federal"))

        # State AGs and PDs (all 50 states)
        states = [
            "Alabama", "Alaska", "Arizona", "Arkansas", "California",
            "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
            "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
            "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
            "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
            "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
            "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
            "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
            "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
            "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
        ]
        for state in states:
            self._firms.append(FirmRecord(
                canonical_name=f"{state} Attorney General's Office",
                category="state_ag",
            ))
            self._firms.append(FirmRecord(
                canonical_name=f"{state} State Public Defender's Office",
                category="state_pd",
            ))

        # Legal aid
        legal_aid = [
            "American Civil Liberties Union (ACLU)",
            "Electronic Frontier Foundation (EFF)",
            "NAACP Legal Defense Fund",
            "Southern Poverty Law Center",
            "Lambda Legal",
            "Innocence Project",
            "Legal Aid Society",
            "National Women's Law Center",
            "Brennan Center for Justice",
            "Institute for Justice",
        ]
        for name in legal_aid:
            self._firms.append(FirmRecord(canonical_name=name, category="legal_aid"))

    def lookup(self, name: str, threshold: float = 0.6) -> Optional[FirmRecord]:
        """Look up a firm by name with fuzzy matching."""
        if not name:
            return None

        # Exact match first
        for firm in self._firms:
            if firm.canonical_name.lower() == name.lower():
                return firm

        # Fuzzy match using token Jaccard similarity
        best_match = None
        best_score = 0.0
        name_tokens = _tokenize(name)

        for firm in self._firms:
            firm_tokens = _tokenize(firm.canonical_name)
            score = _jaccard(name_tokens, firm_tokens)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = firm

            # Also check aliases
            for alias in firm.aliases:
                alias_tokens = _tokenize(alias)
                score = _jaccard(name_tokens, alias_tokens)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = firm

        return best_match

    def search(self, query: str, limit: int = 10) -> list[FirmRecord]:
        """Search firms by partial name match."""
        query_lower = query.lower()
        results = []
        for firm in self._firms:
            if query_lower in firm.canonical_name.lower():
                results.append(firm)
            if len(results) >= limit:
                break
        return results

    def get_by_category(self, category: str) -> list[FirmRecord]:
        """Get all firms in a category."""
        return [f for f in self._firms if f.category == category]

    @property
    def total_count(self) -> int:
        return len(self._firms)


def _tokenize(text: str) -> set[str]:
    """Tokenize a firm name for comparison."""
    text = text.lower()
    text = re.sub(r"[,.\-&']", " ", text)
    tokens = set(text.split())
    # Remove common suffixes
    tokens.discard("llp")
    tokens.discard("llc")
    tokens.discard("pc")
    tokens.discard("pa")
    tokens.discard("sc")
    tokens.discard("the")
    tokens.discard("of")
    tokens.discard("and")
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0
