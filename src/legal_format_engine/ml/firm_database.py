"""Reference database of major law firms and legal organizations.

Enables the ML system to:
1. Normalize firm name variants to canonical forms
2. Match detected firm names against known entities
3. Group documents by firm even with imperfect name detection
4. Know which firms commonly file in which jurisdictions

The builtin database covers Am Law 200, appellate specialists,
government offices, and Wisconsin-specific firms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FirmRecord:
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    firm_type: str = "biglaw"  # biglaw, midlaw, boutique, government, public_defender, legal_aid
    headquarters: str | None = None
    primary_jurisdictions: list[str] = field(default_factory=list)
    practice_areas: list[str] = field(default_factory=list)
    am_law_rank: int | None = None
    notable: str | None = None

    def to_dict(self) -> dict:
        return {
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "firm_type": self.firm_type,
            "headquarters": self.headquarters,
            "primary_jurisdictions": self.primary_jurisdictions,
            "practice_areas": self.practice_areas,
            "am_law_rank": self.am_law_rank,
            "notable": self.notable,
        }


class FirmDatabase:
    """Searchable database of law firms with fuzzy matching."""

    def __init__(self) -> None:
        self._firms: dict[str, FirmRecord] = {}
        self._alias_map: dict[str, str] = {}  # lowercase normalized -> canonical
        self._load_builtin()

    def lookup(self, name: str) -> FirmRecord | None:
        """Look up a firm by any name variant."""
        key = self._normalize_key(name)
        canonical = self._alias_map.get(key)
        if canonical:
            return self._firms.get(canonical)
        # Try fuzzy
        match = self._fuzzy_match(name)
        if match:
            return self._firms.get(match)
        return None

    def normalize_name(self, raw_name: str) -> str:
        """Normalize a detected firm name to its canonical form."""
        record = self.lookup(raw_name)
        return record.canonical_name if record else raw_name

    def search(self, query: str) -> list[FirmRecord]:
        """Search firms by partial name match."""
        query_lower = query.lower()
        results = []
        for record in self._firms.values():
            if query_lower in record.canonical_name.lower():
                results.append(record)
                continue
            for alias in record.aliases:
                if query_lower in alias.lower():
                    results.append(record)
                    break
        return results

    def by_jurisdiction(self, jurisdiction: str) -> list[FirmRecord]:
        """Get firms that commonly file in a jurisdiction."""
        j = jurisdiction.lower()
        return [
            r for r in self._firms.values()
            if j in [x.lower() for x in r.primary_jurisdictions]
        ]

    def by_type(self, firm_type: str) -> list[FirmRecord]:
        return [r for r in self._firms.values() if r.firm_type == firm_type]

    def all_firms(self) -> list[FirmRecord]:
        return list(self._firms.values())

    def add_firm(self, record: FirmRecord) -> None:
        """Add a firm to the database."""
        self._firms[record.canonical_name] = record
        self._index_firm(record)

    def _index_firm(self, record: FirmRecord) -> None:
        key = self._normalize_key(record.canonical_name)
        self._alias_map[key] = record.canonical_name
        for alias in record.aliases:
            akey = self._normalize_key(alias)
            self._alias_map[akey] = record.canonical_name

    @staticmethod
    def _normalize_key(name: str) -> str:
        """Normalize a name for lookup: lowercase, strip suffixes, punctuation."""
        s = name.lower().strip()
        # Strip entity suffixes
        s = re.sub(r'\b(l\.?l\.?p\.?|l\.?l\.?c\.?|p\.?c\.?|p\.?l\.?l\.?c\.?|'
                   r'p\.?a\.?|s\.?c\.?|ltd\.?|inc\.?|l\.?p\.?)\b', '', s, flags=re.I)
        # Normalize & and "and"
        s = s.replace('&', 'and')
        # Remove punctuation except spaces
        s = re.sub(r'[^a-z0-9\s]', '', s)
        # Collapse whitespace
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def _fuzzy_match(self, name: str, threshold: float = 0.75) -> str | None:
        """Token-based fuzzy matching."""
        name_tokens = set(self._normalize_key(name).split())
        if not name_tokens:
            return None

        best_score = 0.0
        best_match = None

        for canonical, record in self._firms.items():
            canon_tokens = set(self._normalize_key(canonical).split())
            if not canon_tokens:
                continue
            # Jaccard similarity
            intersection = name_tokens & canon_tokens
            union = name_tokens | canon_tokens
            score = len(intersection) / len(union) if union else 0
            if score > best_score and score >= threshold:
                best_score = score
                best_match = canonical

        return best_match

    def _load_builtin(self) -> None:
        """Load the builtin firm database."""
        for record in _BUILTIN_FIRMS:
            self._firms[record.canonical_name] = record
            self._index_firm(record)


# ---------------------------------------------------------------------------
# Builtin firm records
# ---------------------------------------------------------------------------

def _f(name, aliases=None, ftype="biglaw", hq=None, jurisdictions=None,
       areas=None, rank=None, notable=None):
    """Shorthand factory for FirmRecord."""
    return FirmRecord(
        canonical_name=name,
        aliases=aliases or [],
        firm_type=ftype,
        headquarters=hq,
        primary_jurisdictions=jurisdictions or [],
        practice_areas=areas or ["litigation", "appellate"],
        am_law_rank=rank,
        notable=notable,
    )


_BUILTIN_FIRMS: list[FirmRecord] = [
    # === AM LAW TOP 50 ===
    _f("Kirkland & Ellis", ["Kirkland & Ellis LLP", "Kirkland", "K&E"],
       hq="Chicago, IL", jurisdictions=["illinois", "new_york", "federal"],
       rank=1, notable="Largest US firm by revenue"),
    _f("Latham & Watkins", ["Latham & Watkins LLP", "Latham"],
       hq="Los Angeles, CA", jurisdictions=["california", "new_york", "federal"],
       rank=2),
    _f("DLA Piper", ["DLA Piper LLP", "DLA"],
       hq="Multiple", jurisdictions=["new_york", "california", "federal"],
       rank=3, notable="Largest firm by headcount"),
    _f("Baker McKenzie", ["Baker & McKenzie", "Baker McKenzie LLP", "BakerMcKenzie"],
       hq="Chicago, IL", jurisdictions=["illinois", "federal"], rank=4),
    _f("Skadden, Arps, Slate, Meagher & Flom",
       ["Skadden Arps", "Skadden", "SKADDEN", "Skadden LLP"],
       hq="New York, NY", jurisdictions=["new_york", "federal"],
       rank=5, notable="Premier M&A and litigation firm"),
    _f("Sidley Austin", ["Sidley Austin LLP", "Sidley"],
       hq="Chicago, IL", jurisdictions=["illinois", "new_york", "federal"], rank=6),
    _f("Morgan, Lewis & Bockius", ["Morgan Lewis", "Morgan Lewis LLP"],
       hq="Philadelphia, PA", jurisdictions=["pennsylvania", "new_york", "federal"], rank=7),
    _f("Jones Day", ["JONES DAY", "Jones, Day"],
       hq="Cleveland, OH", jurisdictions=["ohio", "new_york", "federal"],
       rank=8, notable="No partnership structure"),
    _f("White & Case", ["White & Case LLP", "White and Case"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=9),
    _f("Greenberg Traurig", ["Greenberg Traurig LLP", "Greenberg Traurig PA", "GT"],
       hq="Miami, FL", jurisdictions=["florida", "new_york", "federal"], rank=10),
    _f("Gibson, Dunn & Crutcher", ["Gibson Dunn", "Gibson Dunn LLP"],
       hq="Los Angeles, CA", jurisdictions=["california", "new_york", "federal"],
       rank=11, notable="Top appellate and SCOTUS practice"),
    _f("Sullivan & Cromwell", ["Sullivan & Cromwell LLP", "S&C", "Sullivan Cromwell"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=12),
    _f("Hogan Lovells", ["Hogan Lovells LLP", "Hogan Lovells US LLP"],
       hq="Washington, DC", jurisdictions=["federal", "virginia"], rank=13),
    _f("Weil, Gotshal & Manges", ["Weil Gotshal", "Weil", "Weil LLP"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=14),
    _f("Davis Polk & Wardwell", ["Davis Polk", "Davis Polk LLP"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=15),
    _f("Cleary Gottlieb Steen & Hamilton",
       ["Cleary Gottlieb", "Cleary", "CGSH"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=16),
    _f("Cravath, Swaine & Moore", ["Cravath", "Cravath Swaine", "Cravath LLP"],
       hq="New York, NY", jurisdictions=["new_york", "federal"],
       rank=17, notable="Originator of the Cravath system"),
    _f("Paul, Weiss, Rifkind, Wharton & Garrison",
       ["Paul Weiss", "Paul Weiss LLP", "PWRWG"],
       hq="New York, NY", jurisdictions=["new_york", "federal"],
       rank=18, notable="Top appellate practice; Kannon Shanmugam"),
    _f("Simpson Thacher & Bartlett", ["Simpson Thacher", "STB"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=19),
    _f("Debevoise & Plimpton", ["Debevoise", "Debevoise LLP"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=20),
    _f("Covington & Burling", ["Covington", "Covington LLP"],
       hq="Washington, DC", jurisdictions=["federal", "virginia"], rank=21),
    _f("Mayer Brown", ["Mayer Brown LLP"],
       hq="Chicago, IL", jurisdictions=["illinois", "new_york", "federal"], rank=22),
    _f("King & Spalding", ["King & Spalding LLP", "King Spalding"],
       hq="Atlanta, GA", jurisdictions=["georgia", "new_york", "federal"], rank=23),
    _f("Ropes & Gray", ["Ropes & Gray LLP", "Ropes Gray"],
       hq="Boston, MA", jurisdictions=["massachusetts", "new_york", "federal"], rank=24),
    _f("Morrison & Foerster", ["Morrison Foerster", "MoFo", "Morrison & Foerster LLP"],
       hq="San Francisco, CA", jurisdictions=["california", "new_york", "federal"], rank=25),
    _f("Willkie Farr & Gallagher", ["Willkie Farr", "Willkie"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=26),
    _f("WilmerHale", ["Wilmer Cutler Pickering Hale and Dorr", "Wilmer Hale", "WilmerHale LLP"],
       hq="Washington, DC", jurisdictions=["federal", "massachusetts"],
       rank=27, notable="Major SCOTUS practice"),
    _f("Perkins Coie", ["Perkins Coie LLP"],
       hq="Seattle, WA", jurisdictions=["washington", "federal"], rank=28),
    _f("Arnold & Porter", ["Arnold & Porter Kaye Scholer", "Arnold Porter"],
       hq="Washington, DC", jurisdictions=["federal", "new_york"], rank=29),
    _f("Akin Gump Strauss Hauer & Feld",
       ["Akin Gump", "Akin Gump LLP", "AGSHF"],
       hq="Washington, DC", jurisdictions=["federal", "texas"], rank=30),
    _f("Quinn Emanuel Urquhart & Sullivan",
       ["Quinn Emanuel", "Quinn", "QEUS"],
       hq="Los Angeles, CA", jurisdictions=["california", "new_york", "federal"],
       rank=31, notable="Litigation-only firm"),
    _f("Orrick, Herrington & Sutcliffe", ["Orrick", "Orrick LLP"],
       hq="San Francisco, CA", jurisdictions=["california", "federal"], rank=32),
    _f("Norton Rose Fulbright", ["Norton Rose", "Norton Rose Fulbright US LLP", "Fulbright"],
       hq="Houston, TX", jurisdictions=["texas", "federal"], rank=33),
    _f("Proskauer Rose", ["Proskauer", "Proskauer Rose LLP"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=34),
    _f("Milbank", ["Milbank LLP", "Milbank Tweed"],
       hq="New York, NY", jurisdictions=["new_york", "federal"], rank=35),
    _f("Wachtell, Lipton, Rosen & Katz",
       ["Wachtell Lipton", "Wachtell", "WLRK"],
       hq="New York, NY", jurisdictions=["new_york", "federal"],
       rank=36, notable="Highest profits per partner"),
    _f("Cooley", ["Cooley LLP", "Cooley Godward"],
       hq="Palo Alto, CA", jurisdictions=["california", "federal"], rank=37),
    _f("Foley & Lardner", ["Foley & Lardner LLP", "Foley Lardner", "Foley"],
       hq="Milwaukee, WI", jurisdictions=["wisconsin", "federal", "illinois"],
       rank=38, notable="Milwaukee HQ; major Wisconsin filer"),
    _f("Holland & Knight", ["Holland & Knight LLP", "Holland Knight"],
       hq="Tampa, FL", jurisdictions=["florida", "federal"], rank=39),
    _f("Katten Muchin Rosenman", ["Katten Muchin", "Katten", "Katten LLP"],
       hq="Chicago, IL", jurisdictions=["illinois", "federal"], rank=40),
    _f("Reed Smith", ["Reed Smith LLP"],
       hq="Pittsburgh, PA", jurisdictions=["pennsylvania", "federal"], rank=41),
    _f("Dechert", ["Dechert LLP"],
       hq="Philadelphia, PA", jurisdictions=["pennsylvania", "federal"], rank=42),
    _f("McDermott Will & Emery", ["McDermott", "McDermott Will", "MWE"],
       hq="Chicago, IL", jurisdictions=["illinois", "federal"], rank=43),
    _f("Goodwin Procter", ["Goodwin", "Goodwin Procter LLP"],
       hq="Boston, MA", jurisdictions=["massachusetts", "federal"], rank=44),
    _f("Pillsbury Winthrop Shaw Pittman",
       ["Pillsbury Winthrop", "Pillsbury", "Pillsbury LLP"],
       hq="San Francisco, CA", jurisdictions=["california", "federal"], rank=45),
    _f("Vinson & Elkins", ["Vinson & Elkins LLP", "V&E"],
       hq="Houston, TX", jurisdictions=["texas", "federal"], rank=46),
    _f("Alston & Bird", ["Alston & Bird LLP", "Alston Bird"],
       hq="Atlanta, GA", jurisdictions=["georgia", "federal"], rank=47),
    _f("Hunton Andrews Kurth", ["Hunton Andrews", "Hunton"],
       hq="Richmond, VA", jurisdictions=["virginia", "federal"], rank=48),
    _f("McGuireWoods", ["McGuireWoods LLP"],
       hq="Richmond, VA", jurisdictions=["virginia", "federal"], rank=49),
    _f("Winston & Strawn", ["Winston & Strawn LLP", "Winston Strawn"],
       hq="Chicago, IL", jurisdictions=["illinois", "federal"], rank=50),

    # === AM LAW 51-100 (selected major filers) ===
    _f("Jenner & Block", ["Jenner & Block LLP", "Jenner Block"],
       hq="Chicago, IL", jurisdictions=["illinois", "federal"],
       rank=55, notable="Top appellate practice"),
    _f("O'Melveny & Myers", ["O'Melveny", "OMM", "O'Melveny LLP"],
       hq="Los Angeles, CA", jurisdictions=["california", "federal"], rank=56),
    _f("Sheppard Mullin", ["Sheppard Mullin Richter & Hampton", "Sheppard Mullin LLP"],
       hq="Los Angeles, CA", jurisdictions=["california", "federal"], rank=58),
    _f("Faegre Drinker Biddle & Reath",
       ["Faegre Drinker", "Faegre Baker Daniels", "Quarles & Brady"],
       hq="Minneapolis, MN", jurisdictions=["minnesota", "wisconsin", "indiana", "federal"],
       rank=60, notable="Absorbed Quarles & Brady (Milwaukee)"),
    _f("Steptoe & Johnson", ["Steptoe", "Steptoe LLP"],
       hq="Washington, DC", jurisdictions=["federal", "west_virginia"], rank=62),
    _f("Crowell & Moring", ["Crowell", "Crowell LLP"],
       hq="Washington, DC", jurisdictions=["federal"], rank=65),
    _f("Seyfarth Shaw", ["Seyfarth Shaw LLP", "Seyfarth"],
       hq="Chicago, IL", jurisdictions=["illinois", "federal"], rank=68),
    _f("Polsinelli", ["Polsinelli PC"],
       hq="Kansas City, MO", jurisdictions=["missouri", "federal"], rank=70),
    _f("Baker Botts", ["Baker Botts LLP"],
       hq="Houston, TX", jurisdictions=["texas", "federal"], rank=72),
    _f("Squire Patton Boggs", ["Squire Patton Boggs LLP", "Squire Sanders"],
       hq="Cleveland, OH", jurisdictions=["ohio", "federal"], rank=75),
    _f("Littler Mendelson", ["Littler", "Littler Mendelson PC"],
       hq="San Francisco, CA", jurisdictions=["california", "federal"], rank=78),
    _f("Blank Rome", ["Blank Rome LLP"],
       hq="Philadelphia, PA", jurisdictions=["pennsylvania", "federal"], rank=80),
    _f("Bryan Cave Leighton Paisner", ["Bryan Cave", "BCLP"],
       hq="St. Louis, MO", jurisdictions=["missouri", "federal"], rank=82),
    _f("Troutman Pepper Hamilton Sanders",
       ["Troutman Pepper", "Troutman Sanders", "Pepper Hamilton"],
       hq="Atlanta, GA", jurisdictions=["georgia", "pennsylvania", "federal"], rank=85),

    # === APPELLATE SPECIALISTS ===
    _f("Goldstein & Russell", ["Goldstein Russell", "Goldstein & Russell PC"],
       ftype="boutique", hq="Washington, DC", jurisdictions=["federal"],
       areas=["appellate", "scotus"],
       notable="SCOTUS specialist; manages SCOTUSblog"),
    _f("Bancroft PLLC", ["Bancroft"],
       ftype="boutique", hq="Washington, DC", jurisdictions=["federal"],
       areas=["appellate", "scotus"]),
    _f("MoloLamken", ["MoloLamken LLP"],
       ftype="boutique", hq="Washington, DC", jurisdictions=["federal"],
       areas=["appellate", "litigation"]),
    _f("Clement & Murphy", ["Clement & Murphy PLLC", "Clement Murphy"],
       ftype="boutique", hq="Washington, DC", jurisdictions=["federal"],
       areas=["appellate", "scotus"],
       notable="Paul Clement, former US Solicitor General"),
    _f("Consovoy McCarthy", ["Consovoy McCarthy PLLC"],
       ftype="boutique", hq="Arlington, VA", jurisdictions=["federal"],
       areas=["appellate", "constitutional"]),
    _f("Williams & Connolly", ["Williams & Connolly LLP", "Williams Connolly"],
       ftype="boutique", hq="Washington, DC", jurisdictions=["federal"],
       areas=["litigation", "appellate"],
       notable="Premier trial and appellate litigation"),
    _f("Kellogg, Hansen, Todd, Figel & Frederick",
       ["Kellogg Hansen", "KHTFF"],
       ftype="boutique", hq="Washington, DC", jurisdictions=["federal"],
       areas=["appellate", "scotus"]),
    _f("Robbins, Russell, Englert, Orseck, Untereiner & Sauber",
       ["Robbins Russell", "RREOUS"],
       ftype="boutique", hq="Washington, DC", jurisdictions=["federal"],
       areas=["appellate", "scotus"]),

    # === WISCONSIN-SPECIFIC ===
    _f("Michael Best & Friedrich", ["Michael Best", "Michael Best LLP"],
       ftype="midlaw", hq="Milwaukee, WI",
       jurisdictions=["wisconsin", "federal"]),
    _f("Reinhart Boerner Van Deuren",
       ["Reinhart", "Reinhart Boerner", "Reinhart Law"],
       ftype="midlaw", hq="Milwaukee, WI",
       jurisdictions=["wisconsin", "federal"]),
    _f("von Briesen & Roper", ["von Briesen", "von Briesen SC"],
       ftype="midlaw", hq="Milwaukee, WI",
       jurisdictions=["wisconsin"]),
    _f("Godfrey & Kahn", ["Godfrey Kahn", "Godfrey & Kahn SC"],
       ftype="midlaw", hq="Milwaukee, WI",
       jurisdictions=["wisconsin", "federal"]),
    _f("Husch Blackwell", ["Husch Blackwell LLP"],
       ftype="midlaw", hq="Kansas City, MO",
       jurisdictions=["wisconsin", "missouri", "federal"]),
    _f("Stafford Rosenbaum", ["Stafford Rosenbaum LLP"],
       ftype="midlaw", hq="Madison, WI", jurisdictions=["wisconsin"]),
    _f("Axley Brynelson", ["Axley", "Axley Brynelson LLP"],
       ftype="midlaw", hq="Madison, WI", jurisdictions=["wisconsin"]),
    _f("Boardman & Clark", ["Boardman Clark", "Boardman & Clark LLP"],
       ftype="midlaw", hq="Madison, WI", jurisdictions=["wisconsin"]),
    _f("DeWitt LLP", ["DeWitt Ross & Stevens", "DeWitt"],
       ftype="midlaw", hq="Madison, WI", jurisdictions=["wisconsin"]),
    _f("Whyte Hirschboeck Dudek",
       ["WHD", "Whyte Hirschboeck", "Husch Blackwell (fka WHD)"],
       ftype="midlaw", hq="Milwaukee, WI", jurisdictions=["wisconsin"],
       notable="Merged into Husch Blackwell"),

    # === GOVERNMENT — FEDERAL ===
    _f("United States Department of Justice",
       ["US DOJ", "DOJ", "U.S. Department of Justice", "Department of Justice",
        "United States Attorney General"],
       ftype="government", hq="Washington, DC", jurisdictions=["federal"],
       areas=["litigation", "appellate", "criminal"],
       notable="Federal government litigation arm"),
    _f("Office of the Solicitor General",
       ["Solicitor General", "SG", "OSG", "US Solicitor General"],
       ftype="government", hq="Washington, DC", jurisdictions=["federal"],
       areas=["appellate", "scotus"],
       notable="Represents US before SCOTUS"),
    _f("Federal Public Defender",
       ["Federal Public Defender's Office", "FPD", "Office of the Federal Public Defender"],
       ftype="public_defender", hq="Multiple", jurisdictions=["federal"],
       areas=["criminal", "appellate"]),

    # === GOVERNMENT — STATE AG OFFICES (all 50) ===
    *[_f(f"{state} Attorney General",
         [f"{state} AG", f"{state} Department of Justice",
          f"{state} DOJ", f"Office of the Attorney General of {state}",
          f"{state} AG's Office"],
         ftype="government", jurisdictions=[state.lower().replace(" ", "_")],
         areas=["litigation", "appellate", "criminal"])
      for state in [
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
      ]],

    # === GOVERNMENT — STATE PUBLIC DEFENDERS (all 50) ===
    *[_f(f"{state} State Public Defender",
         [f"{state} Public Defender", f"{state} SPD",
          f"Office of the State Public Defender ({state})",
          f"{state} Office of the Public Defender"],
         ftype="public_defender",
         jurisdictions=[state.lower().replace(" ", "_")],
         areas=["criminal", "appellate"])
      for state in [
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
      ]],

    # === LEGAL AID (selected major organizations) ===
    _f("Legal Aid Society", ["Legal Aid Society of New York", "LAS"],
       ftype="legal_aid", hq="New York, NY", jurisdictions=["new_york"],
       areas=["criminal", "civil", "appellate"]),
    _f("ACLU", ["American Civil Liberties Union", "ACLU Foundation"],
       ftype="legal_aid", hq="New York, NY", jurisdictions=["federal"],
       areas=["constitutional", "appellate"]),
    _f("NAACP Legal Defense Fund",
       ["LDF", "NAACP LDF", "Legal Defense and Educational Fund"],
       ftype="legal_aid", hq="New York, NY", jurisdictions=["federal"],
       areas=["civil_rights", "appellate"]),
    _f("Innocence Project", [],
       ftype="legal_aid", hq="New York, NY", jurisdictions=["federal"],
       areas=["criminal", "appellate"]),
    _f("Public Citizen Litigation Group", ["Public Citizen"],
       ftype="legal_aid", hq="Washington, DC", jurisdictions=["federal"],
       areas=["consumer", "appellate"]),
    _f("Institute for Justice", ["IJ"],
       ftype="legal_aid", hq="Arlington, VA", jurisdictions=["federal"],
       areas=["constitutional", "appellate"]),
    _f("Lambda Legal", ["Lambda Legal Defense and Education Fund"],
       ftype="legal_aid", hq="New York, NY", jurisdictions=["federal"],
       areas=["civil_rights", "appellate"]),
    _f("Electronic Frontier Foundation", ["EFF"],
       ftype="legal_aid", hq="San Francisco, CA", jurisdictions=["federal"],
       areas=["technology", "appellate"]),
    _f("Wisconsin Judicare", ["Judicare"],
       ftype="legal_aid", hq="Wausau, WI", jurisdictions=["wisconsin"],
       areas=["civil", "appellate"]),
    _f("Legal Action of Wisconsin", ["Legal Action"],
       ftype="legal_aid", hq="Milwaukee, WI", jurisdictions=["wisconsin"],
       areas=["civil", "appellate"]),
]
