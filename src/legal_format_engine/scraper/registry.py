"""Registry of known court e-filing portals and their requirements pages.

This is the authoritative catalog of where to find e-filing requirements
for each jurisdiction. Sources are categorized by tier and include
the specific URLs where formatting rules are published.

Registry entries are manually curated from verified official sources.
The discovery module can propose new entries, but they must be validated
before being added here.
"""

from __future__ import annotations

from legal_format_engine.scraper.models import CourtLevel, CourtSystem, SourceTier


class _RegistryEntry:
    """Internal registry entry for a jurisdiction's court system."""

    __slots__ = (
        "jurisdiction", "jurisdiction_name", "state", "court_name",
        "level", "efiling_portal_url", "efiling_vendor",
        "efiling_system_name", "requirements_urls", "source_tier",
        "parent_system", "notes",
    )

    def __init__(
        self,
        *,
        jurisdiction: str,
        jurisdiction_name: str,
        state: str | None = None,
        court_name: str,
        level: CourtLevel,
        efiling_portal_url: str | None = None,
        efiling_vendor: str | None = None,
        efiling_system_name: str | None = None,
        requirements_urls: list[str] | None = None,
        source_tier: SourceTier = SourceTier.OFFICIAL,
        parent_system: str | None = None,
        notes: str = "",
    ) -> None:
        self.jurisdiction = jurisdiction
        self.jurisdiction_name = jurisdiction_name
        self.state = state
        self.court_name = court_name
        self.level = level
        self.efiling_portal_url = efiling_portal_url
        self.efiling_vendor = efiling_vendor
        self.efiling_system_name = efiling_system_name
        self.requirements_urls = requirements_urls or []
        self.source_tier = source_tier
        self.parent_system = parent_system
        self.notes = notes

    def to_court_system(self) -> CourtSystem:
        return CourtSystem(
            name=self.court_name,
            jurisdiction=self.jurisdiction,
            state=self.state,
            level=self.level,
            parent_system=self.parent_system,
            efiling_portal_url=self.efiling_portal_url,
            efiling_vendor=self.efiling_vendor,
            efiling_system_name=self.efiling_system_name,
            requirements_urls=self.requirements_urls,
        )


# ---------------------------------------------------------------------------
# The Registry
# ---------------------------------------------------------------------------

_REGISTRY: list[_RegistryEntry] = [
    # -----------------------------------------------------------------------
    # WISCONSIN
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="WI",
        jurisdiction_name="Wisconsin",
        state="WI",
        court_name="Wisconsin Circuit Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://efiling.wicourts.gov",
        efiling_vendor="Tyler Technologies",
        efiling_system_name="Odyssey File & Serve",
        requirements_urls=[
            # Tyler Technologies help portal for WI e-filing (quasi-official)
            "https://efilinghelp.zendesk.com/hc/en-us/articles/25044580029965",
            # Wisconsin court system official e-filing page
            "https://www.wicourts.gov/ecourts/efilecircuit.htm",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Wisconsin Court System",
        notes="Proposed orders: 3-inch top margin, .docx format, no judge signature block",
    ),
    _RegistryEntry(
        jurisdiction="WI",
        jurisdiction_name="Wisconsin",
        state="WI",
        court_name="Wisconsin Court of Appeals",
        level=CourtLevel.APPELLATE,
        efiling_portal_url="https://efiling.wicourts.gov",
        efiling_vendor="Tyler Technologies",
        efiling_system_name="Odyssey File & Serve",
        requirements_urls=[
            "https://www.wicourts.gov/ecourts/efileappellate.htm",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Wisconsin Court System",
    ),
    _RegistryEntry(
        jurisdiction="WI",
        jurisdiction_name="Wisconsin",
        state="WI",
        court_name="Wisconsin Supreme Court",
        level=CourtLevel.SUPREME,
        efiling_portal_url="https://efiling.wicourts.gov",
        efiling_vendor="Tyler Technologies",
        efiling_system_name="Odyssey File & Serve",
        requirements_urls=[
            "https://www.wicourts.gov/ecourts/efileappellate.htm",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Wisconsin Court System",
    ),

    # -----------------------------------------------------------------------
    # FEDERAL
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="US-FED",
        jurisdiction_name="United States Federal Courts",
        court_name="Federal District Courts (CM/ECF)",
        level=CourtLevel.DISTRICT,
        efiling_portal_url="https://pacer.uscourts.gov",
        efiling_vendor="Administrative Office of the US Courts",
        efiling_system_name="CM/ECF",
        requirements_urls=[
            "https://www.uscourts.gov/court-records/electronic-filing-cmecf",
            "https://www.uscourts.gov/rules-policies/current-rules-practice-procedure",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="United States Courts",
    ),

    # -----------------------------------------------------------------------
    # CALIFORNIA
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="CA",
        jurisdiction_name="California",
        state="CA",
        court_name="California Superior Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://www.courts.ca.gov/42702.htm",
        efiling_vendor="Various (by county)",
        efiling_system_name="Various",
        requirements_urls=[
            "https://www.courts.ca.gov/documents/adopt-20220701-CRC02.pdf",
            "https://www.courts.ca.gov/42702.htm",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="California Courts",
        notes="California Rules of Court, Title 2 (Trial Court Rules), Division 4",
    ),

    # -----------------------------------------------------------------------
    # TEXAS
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="TX",
        jurisdiction_name="Texas",
        state="TX",
        court_name="Texas District Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://efiletexas.gov",
        efiling_vendor="Tyler Technologies",
        efiling_system_name="eFileTexas",
        requirements_urls=[
            "https://www.txcourts.gov/rules-forms/rules-standards/",
            "https://efiletexas.gov/service-providers.htm",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Texas Courts",
        notes="Mandatory e-filing statewide since 2014 for civil cases",
    ),

    # -----------------------------------------------------------------------
    # NEW YORK
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="NY",
        jurisdiction_name="New York",
        state="NY",
        court_name="New York Supreme Court (NYSCEF)",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://iapps.courts.state.ny.us/nyscef/",
        efiling_vendor="NYS Office of Court Administration",
        efiling_system_name="NYSCEF",
        requirements_urls=[
            "https://iapps.courts.state.ny.us/nyscef/Filing",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="New York State Unified Court System",
    ),

    # -----------------------------------------------------------------------
    # ILLINOIS
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="IL",
        jurisdiction_name="Illinois",
        state="IL",
        court_name="Illinois Circuit Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://efile.illinoiscourts.gov",
        efiling_vendor="Tyler Technologies",
        efiling_system_name="Odyssey eFileIL",
        requirements_urls=[
            "https://www.illinoiscourts.gov/courts/supreme-court/supreme-court-rules/",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Illinois Courts",
    ),

    # -----------------------------------------------------------------------
    # FLORIDA
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="FL",
        jurisdiction_name="Florida",
        state="FL",
        court_name="Florida Circuit Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://www.myflcourtaccess.com",
        efiling_vendor="CivicPlus (formerly FACC/OnBase)",
        efiling_system_name="Florida Courts E-Filing Portal",
        requirements_urls=[
            "https://www.flcourts.gov/Resources-Services/Court-Technology/E-Filing-Portal",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Florida Courts",
    ),

    # -----------------------------------------------------------------------
    # MINNESOTA (neighbor to WI, similar Tyler system)
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="MN",
        jurisdiction_name="Minnesota",
        state="MN",
        court_name="Minnesota District Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://minnesota.tylerhost.net/ofsweb",
        efiling_vendor="Tyler Technologies",
        efiling_system_name="Odyssey File & Serve",
        requirements_urls=[
            "https://www.mncourts.gov/eFiling.aspx",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Minnesota Judicial Branch",
    ),

    # -----------------------------------------------------------------------
    # MICHIGAN (neighbor to WI)
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="MI",
        jurisdiction_name="Michigan",
        state="MI",
        court_name="Michigan Circuit/District Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://mifile.courts.michigan.gov",
        efiling_vendor="ImageSoft/Tyler Technologies",
        efiling_system_name="MiFILE",
        requirements_urls=[
            "https://www.courts.michigan.gov/administration/trial-court/efiling/",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Michigan Courts",
    ),

    # -----------------------------------------------------------------------
    # IOWA (neighbor to WI)
    # -----------------------------------------------------------------------
    _RegistryEntry(
        jurisdiction="IA",
        jurisdiction_name="Iowa",
        state="IA",
        court_name="Iowa District Court",
        level=CourtLevel.CIRCUIT,
        efiling_portal_url="https://www.iowacourts.gov/for-lawyers/electronic-filing",
        efiling_vendor="Tyler Technologies",
        efiling_system_name="EDMS",
        requirements_urls=[
            "https://www.iowacourts.gov/for-lawyers/electronic-filing",
        ],
        source_tier=SourceTier.OFFICIAL,
        parent_system="Iowa Judicial Branch",
    ),
]


class JurisdictionRegistry:
    """Registry of known court e-filing systems and their requirements pages.

    Provides lookup by jurisdiction, state, court level, and e-filing vendor.
    """

    def __init__(self) -> None:
        self._entries = list(_REGISTRY)

    @property
    def jurisdictions(self) -> list[str]:
        """All known jurisdiction codes."""
        return sorted(set(e.jurisdiction for e in self._entries))

    @property
    def states(self) -> list[str]:
        """All US states with registered courts."""
        return sorted(set(e.state for e in self._entries if e.state))

    def by_jurisdiction(self, jurisdiction: str) -> list[CourtSystem]:
        """Get all court systems for a jurisdiction code (e.g., 'WI')."""
        return [
            e.to_court_system()
            for e in self._entries
            if e.jurisdiction == jurisdiction
        ]

    def by_state(self, state: str) -> list[CourtSystem]:
        """Get all court systems for a US state abbreviation."""
        return [
            e.to_court_system()
            for e in self._entries
            if e.state == state
        ]

    def by_level(self, level: CourtLevel) -> list[CourtSystem]:
        """Get all court systems at a specific level."""
        return [
            e.to_court_system()
            for e in self._entries
            if e.level == level
        ]

    def by_vendor(self, vendor: str) -> list[CourtSystem]:
        """Get all court systems using a specific e-filing vendor."""
        vendor_lower = vendor.lower()
        return [
            e.to_court_system()
            for e in self._entries
            if e.efiling_vendor and vendor_lower in e.efiling_vendor.lower()
        ]

    def all_requirements_urls(self) -> dict[str, list[str]]:
        """Get all known requirements page URLs grouped by jurisdiction."""
        result: dict[str, list[str]] = {}
        for entry in self._entries:
            if entry.requirements_urls:
                urls = result.setdefault(entry.jurisdiction, [])
                for url in entry.requirements_urls:
                    if url not in urls:
                        urls.append(url)
        return result

    def all_courts(self) -> list[CourtSystem]:
        """Get all registered court systems."""
        return [e.to_court_system() for e in self._entries]

    def add_entry(
        self,
        *,
        jurisdiction: str,
        jurisdiction_name: str,
        state: str | None = None,
        court_name: str,
        level: CourtLevel,
        efiling_portal_url: str | None = None,
        efiling_vendor: str | None = None,
        efiling_system_name: str | None = None,
        requirements_urls: list[str] | None = None,
        source_tier: SourceTier = SourceTier.OFFICIAL,
        parent_system: str | None = None,
    ) -> CourtSystem:
        """Add a new court system to the registry (runtime only)."""
        entry = _RegistryEntry(
            jurisdiction=jurisdiction,
            jurisdiction_name=jurisdiction_name,
            state=state,
            court_name=court_name,
            level=level,
            efiling_portal_url=efiling_portal_url,
            efiling_vendor=efiling_vendor,
            efiling_system_name=efiling_system_name,
            requirements_urls=requirements_urls,
            source_tier=source_tier,
            parent_system=parent_system,
        )
        self._entries.append(entry)
        return entry.to_court_system()
