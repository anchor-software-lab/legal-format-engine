# Post-Mortem: Wisconsin Circuit Court Document Generation
## Dunnington Stipulation & Order — Sentence Credit
### Session Date: March 30, 2026
### Case: Forest County Case No. 2024CF000099, State v. Wesley Russell Dunnington

---

## 1. Task Summary

**Objective:** Draft an uncontested Stipulation to Amend Judgment of Conviction (re: sentence credit) and a corresponding proposed Order for eFiling in Forest County Circuit Court, Wisconsin.

**Document types produced:**
- Stipulation (for PDF conversion, wet/electronic signatures by counsel and DA)
- Proposed Order (for eFiling as .docx, digital signature by the court)

**Substantive context:** At sentencing, the State indicated 21 days of credit was appropriate. The circuit court deferred. Trial defense counsel (Breanna Magallones) agreed to research and file a stipulation. She never did. Appellate counsel (Nicholas G. Smith, SPD) is now cleaning it up.

---

## 2. Iteration Log

### Iteration 1: Wrong Template
- **Input:** User provided a prior stipulation/order (McBride, Rock County) as a template.
- **Approach:** Unpack-edit-repack of the McBride .docx XML. Text replacement throughout.
- **Result:** Functional but ugly. The McBride template used Book Antiqua font, a different table structure (Google Docs origin), and a cluttered layout. User rejected: "Garbage in garbage out."
- **Lesson:** Template quality is the ceiling. A bad template cannot be fixed with good substitutions — the underlying XML structure, font choices, spacing, and table layout all carry forward.

### Iteration 2: Better Template (Irwin)
- **Input:** User provided the Irwin stipulation (Taylor County, crime-to-ordinance). Clean Arial font, proper Wisconsin circuit court caption table with "For Official Use" box, professional layout.
- **Approach A (failed):** Attempted to build from scratch using docx-js (Node.js library). Created the caption table programmatically.
- **Result:** The "For Official Use" box rendered at the bottom-right instead of top-right. The `rowSpan` property in docx-js does not produce the same `vMerge` XML that Word uses for vertically merged cells.
- **Lesson:** **docx-js `rowSpan` ≠ Word `vMerge`.** For complex table structures with vertical merges, editing the source XML of a known-good template is far more reliable than generating from scratch. The Irwin template worked in Word because it used `<w:vMerge w:val="restart"/>` and `<w:vMerge/>` continuation cells — docx-js cannot replicate this behavior.

### Iteration 3: XML Editing of Irwin Template
- **Approach:** Unpack the Irwin .docx → edit document.xml directly → repack.
- **Result:** Caption rendered correctly. Body content and signatures functional.
- **Issues discovered in review:**
  1. Duplicate case number (DA Case No. + Court Case No. both converted)
  2. Title too low in caption box (too many spacer paragraphs)
  3. Date field misaligned in signature blocks (underlined tabs vs. underscore characters)

### Iteration 4: Caption Fixes
- **Duplicate case number:** The Irwin template had two case number fields (`DA Case No.` and `Court Case No.`) in separate `<w:p>` elements. Both were text-replaced but neither was removed. Fix: delete the entire second `<w:p>` element.
- **Title position:** 5 empty `<w:p>` spacer paragraphs existed between the case number and the title. Removed 3, keeping 2 for spacing.
- **Lesson:** When adapting a template with more fields than needed, **delete the surplus XML elements entirely** rather than blanking their text content. Empty paragraphs still consume vertical space.

### Iteration 5: Signature Block Alignment
- **Problem:** Using underlined tabs (`<w:u w:val="single"/>` on `<w:tab/>`) for signature and date lines. The underline rendered as a continuous line through the tab stop, but the "Date" text didn't align with the end of the underline. The date underline was also too long — it stretched across the full remaining page width.
- **Root cause:** Tab stops in Word are at fixed positions (every 720 DXA = 0.5"). Underlined tabs create lines of unpredictable length depending on how many tabs are used and where the tab stops fall. The "Date" label floats to the next tab stop after the underline ends, creating a gap.
- **Fix:** Replaced underlined-tab approach with:
  - Underscore characters (`_________________________________`) for signature lines (fixed, predictable width)
  - A single explicit tab stop at 5760 DXA (4") to align "Date" labels
  - Tab character between signature line and date line
- **Lesson:** **Never use underlined tabs for signature lines in generated .docx files.** Use underscore characters or `<w:t>` with explicit underscore strings. Tab-based underlines are fragile across Word versions and screen widths. Underscore characters are deterministic.

### Iteration 6: Proportional Signature Lines
- **Problem:** User noted the DA's signature line was longer than the defense line. This happened because I used more tab characters for Seifert's line (longer name → more tabs to reach "Date").
- **Lesson:** Signature lines should be a **fixed standard length** regardless of name length. Use a consistent number of underscore characters (e.g., 33 underscores = `_________________________________`) for all signature lines. The name appears below the line, not on it.

### Iteration 7: Voice/Perspective in Court Orders
- **Problem:** The order used "Mr. Dunnington" — humanizing language appropriate for defense counsel but not for the court.
- **Fix:** Changed to "the defendant" in the order. The stipulation (counsel's document) retains "Mr. Dunnington."
- **Lesson:** **The court refers to parties by their party title** (the defendant, the State). **Counsel humanizes** by using the client's name (Mr. Dunnington). This is a Wisconsin practice convention that should be encoded as a rule.

### Iteration 8: eFiling Compliance (Proposed Orders)
- **Source:** https://efilinghelp.zendesk.com/hc/en-us/articles/25044580029965
- **Requirements applied:**
  1. 3-inch top margin on first page (4320 DXA) — space for court's digital signature
  2. No judge signature block (no "BY THE COURT:", no signature line, no judge name, no "Dated this" line)
  3. Submit as .docx so the court can edit before signing
- **Lesson:** Proposed orders for eFiling have specific formatting requirements that differ from traditional ink-signed orders. The 3" top margin and absence of judge signature block are mandatory.

---

## 3. Formatting Rules Extracted

### Caption Table Structure (Wisconsin Circuit Court)
- **Grid:** 5 columns (2898 + 1350 + 1080 + 2520 + 2340 DXA)
- **Row 1:** Empty cells with no borders + "For Official Use" cell (vMerge restart, bottom-aligned, centered, 18pt bold Arial)
- **Row 2:** Full-width merged cell (gridSpan=4) with "STATE OF WISCONSIN [tab] CIRCUIT COURT [tab] [COUNTY] COUNTY" (24pt bold Arial, tab stops at center:4050 and right:7542) + vMerge continuation cell
- **Row 3:** Left cell (parties, 22pt Arial) + Right cell (case number + document title, 22pt/22pt bold Arial, centered) + vMerge continuation cell
- **Borders:** Thin single (sz=4) on structural edges; nil on internal cosmetic edges
- **Font:** Arial throughout, 22pt for caption content, 24pt for header line
- **"For Official Use" box:** Right column, vertically merged across all 3 rows, left border only, text bottom-aligned and centered

### Body Text
- **Font:** Arial 24pt (12pt visual)
- **Spacing:** line="276" lineRule="auto" (1.15x line spacing)
- **Alignment:** Justified
- **First-line indent:** 720 DXA (0.5") on substantive paragraphs
- **No numbering** for stipulation/order body (unlike the Irwin amendment stipulation which used numbered paragraphs for multiple terms)

### Signature Blocks
- **Line character:** Underscore (`_`), 33 characters for signature, 18 characters for date
- **Alignment:** Tab stop at 5760 DXA (4") for "Date" column
- **Structure per signatory (3 lines):**
  1. `_________________________________` [tab] `__________________`
  2. `[Name]` [tab] `Date`
  3. `[Title]`
  4. `State Bar No. [number]`
- **/s/ electronic signature:** `/` + italic `s` + `/ [Name]` + trailing spaces, all underlined. Date line follows same tab stop.
- **Line length must be consistent** across all signatories regardless of name length.

### Proposed Order (eFiling)
- **Top margin:** 4320 DXA (3 inches) on first page
- **No signature block for judge** — court applies digitally
- **No "Dated this" line** — court applies
- **File format:** .docx (not PDF)
- **Voice:** Use party titles ("the defendant"), not names

### Stipulation (for PDF conversion)
- **Top margin:** 1080 DXA (0.75 inches) — standard
- **Includes signature blocks** for both counsel and DA
- **Counsel signs with /s/** electronic signature
- **DA line left blank** for wet or electronic signature
- **Voice:** Humanize the client ("Mr. Dunnington")

---

## 4. Technical Lessons (docx XML)

### Template-Based Editing > Generation from Scratch
When replicating an existing document's look and feel, **always unpack and edit the source XML** rather than generating with docx-js. Reasons:
- `vMerge` (vertical cell merge) cannot be reliably produced by docx-js
- Style inheritance, rsid tracking, and font embedding carry forward correctly
- The "For Official Use" box pattern requires exact XML structure that docx-js cannot replicate

### The Unpack-Edit-Repack Workflow
```
1. python scripts/office/unpack.py template.docx unpacked/
2. Edit unpacked/word/document.xml (str_replace or Python script)
3. python scripts/office/pack.py unpacked/ output.docx --original template.docx
```

### Common XML Pitfalls
- **Duplicate bookmark IDs:** When cloning a template for a second document (e.g., order from stipulation template), bookmark IDs from the original persist. The validator catches these — fix by incrementing the `w:id` attribute.
- **Vanish runs:** Wisconsin court system templates (from PROTECT/CCAP) include hidden text runs with `<w:vanish/>` formatting (e.g., `[Defendant Name(s) List]`, `[DACase #]`). These are template placeholders invisible in Word but present in XML. **Always strip vanish runs** when adapting these templates, or they'll appear in some viewers.
- **Smart quotes:** Use XML entities (`&#x2019;` for apostrophes, `&#x201C;`/`&#x201D;` for quotes) when inserting text into existing documents that use smart quotes.

### Margin Settings (DXA units)
- 1 inch = 1440 DXA
- 3 inches = 4320 DXA (eFiling proposed order top margin)
- 0.75 inches = 1080 DXA (standard margins in Irwin template)

---

## 5. Content/Drafting Rules

### Recounting Procedural History in Stipulations
When trial counsel failed to act and the DA was right, frame it neutrally but with the DA's position leading:
- Lead with what the State said (they indicated the correct number)
- Note the court's deferral
- Note trial counsel's commitment to follow up
- State the omission passively ("That stipulation was not subsequently filed")
- Do NOT name trial counsel or assign blame explicitly

**Pattern:**
> At the time of sentencing, the State indicated it believed the defendant was entitled to [X] days of sentence credit. The circuit court deferred final resolution of the credit issue, and trial defense counsel indicated she would research the matter and file a stipulation with the court. That stipulation was not subsequently filed.

### Uncontested Stipulation Structure
1. **Introductory paragraph:** Identify parties and counsel by name and title, end with "hereby stipulate as follows:"
2. **Background paragraph(s):** Procedural history establishing why the stipulation is needed
3. **Operative paragraph:** "The parties now stipulate that the defendant is entitled to [X] days of sentence credit... and respectfully request that the Court enter an order amending the Judgment of Conviction accordingly."

### Order Structure (Sentence Credit Amendment)
1. "Based on the stipulation of the parties,"
2. **IT IS HEREBY ORDERED** (bold) + operative language using party title ("the defendant")

---

## 6. Workflow Recommendations for Future Sessions

1. **Always start with the best available template.** A clean, court-system-native .docx (like the Irwin stipulation) produces dramatically better results than a Google Docs export or a poorly formatted prior document.

2. **Separate documents for stipulation and order.** Even when they share a caption, they serve different filing purposes (PDF vs. .docx eFiling) and have different formatting requirements (margins, signature blocks, voice).

3. **Validate early and often.** Run `pack.py` with validation after each edit pass. XML errors compound.

4. **Use pandoc plain-text extraction** to verify content after packing, but **always visually inspect in Word** — pandoc cannot show table layout, margins, or font rendering.

5. **Bar numbers:** Cannot be reliably found via web search. The Wisconsin State Bar's lawyer search (wisbar.org) and the court system's lawyer history search (lawyerhistory.wicourts.gov) are the authoritative sources but require interactive form submission. Have the user provide bar numbers or look them up directly.

6. **Check eFiling rules** for the specific court system before finalizing proposed orders. Wisconsin's rules (3" top margin, no judge signature block, .docx format) are specific and enforced.

---

## 7. Error Taxonomy for ML Training

| Error Type | Description | Detection Method | Fix Pattern |
|---|---|---|---|
| TEMPLATE_QUALITY | Source template has poor formatting, wrong font, bad structure | Visual inspection of first output | Replace template entirely |
| DUPLICATE_FIELD | Template had N fields, new document needs fewer, surplus fields text-replaced but not deleted | pandoc extraction shows repeated content | Delete entire `<w:p>` elements for surplus fields |
| VMERGE_FAILURE | docx-js rowSpan does not produce Word-compatible vMerge XML | Visual inspection — merged cell renders wrong | Use template XML editing instead of generation |
| TAB_UNDERLINE_MISALIGN | Underlined tabs create lines of unpredictable length; "Date" label doesn't align | Screenshot review | Replace with underscore characters + fixed tab stops |
| PROPORTIONAL_LINE_LENGTH | Signature line length varies with name length | Visual comparison of multiple signature blocks | Use fixed-length underscore strings for all signatories |
| VOICE_MISMATCH | Court order uses counsel's humanizing language | Content review | Court = party titles; Counsel = names |
| EFILING_NONCOMPLIANCE | Missing 3" margin, includes judge signature block | Check against eFiling rules | Apply margin, remove sig block |
| SPACER_PARAGRAPH_EXCESS | Too many empty `<w:p>` elements push content down | Visual inspection of title position | Remove surplus empty paragraphs |
| VANISH_RUN_PERSISTENCE | Hidden template placeholder text persists in output | XML grep for `<w:vanish` | Regex removal of vanish runs |
| BOOKMARK_ID_COLLISION | Duplicate bookmark IDs when reusing template | pack.py validation error | Increment IDs on second instance |

---

## 8. Document Metadata

| Field | Stipulation | Order |
|---|---|---|
| Case | 2024CF000099 | 2024CF000099 |
| County | Forest | Forest |
| Court | Circuit Court | Circuit Court |
| Judge | Leon D. Stenz | Leon D. Stenz |
| Defendant | Wesley Russell Dunnington | Wesley Russell Dunnington |
| Defense Counsel | Nicholas G. Smith, ASPD (Bar 1089586) | N/A |
| Prosecution | Alexander Paul Seifert, DA (Bar [TBD]) | N/A |
| Trial Counsel | Breanna Magallones | N/A |
| Credit Amount | 21 days | 21 days |
| Filing Method | Convert to PDF, file as attachment to proposed order | eFile as .docx proposed order |
| Top Margin | 1080 DXA (0.75") | 4320 DXA (3") |
| Judge Sig Block | N/A | None (court applies digitally) |
| Font | Arial | Arial |
| Template Source | Irwin (Taylor County) crime-to-ordinance stipulation | Same |

---

*Generated from Claude conversation session, March 30, 2026. For use in training the legal document formatting engine.*
