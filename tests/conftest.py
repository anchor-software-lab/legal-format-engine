"""Shared fixtures for legal-format-engine tests."""

import pytest


@pytest.fixture
def sample_wi_efiling_html():
    """Simulated Wisconsin e-filing help page HTML."""
    return """
    <html>
    <head><title>Proposed Orders - Wisconsin eFiling</title></head>
    <body>
    <article class="article-body">
        <h1>Proposed Orders Filing Requirements</h1>
        <p>When submitting a proposed order through the Wisconsin eFiling system,
        please follow these formatting requirements:</p>

        <h2>Formatting Requirements</h2>
        <ul>
            <li>Proposed orders must have a <strong>3-inch top margin</strong>
            on the first page to allow space for the court's digital signature
            and stamp.</li>
            <li>Submit proposed orders in <strong>.docx format</strong> so the
            court can edit the document before signing.</li>
            <li>Do not include a signature line for the judge. The court
            applies its digital signature electronically.</li>
            <li>Maximum file size is 25 MB per document.</li>
        </ul>

        <h2>General Filing Information</h2>
        <p>All documents must be in PDF format unless submitting a proposed
        order. Font should be Arial or Times New Roman, 12pt minimum.</p>
    </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_uscourts_html():
    """Simulated uscourts.gov CM/ECF page HTML."""
    return """
    <html>
    <head><title>Electronic Filing (CM/ECF) - United States Courts</title></head>
    <body>
    <div class="content">
        <h1>Electronic Filing (CM/ECF)</h1>
        <p>The Case Management/Electronic Case Files (CM/ECF) system allows
        attorneys to register and file documents electronically.</p>

        <h2>Filing Requirements</h2>
        <p>All documents must be filed in PDF format. PDFs must be
        text-searchable (not scanned images).</p>
        <p>Maximum file size is 35 MB per document.</p>

        <h2>Related Links</h2>
        <ul>
            <li><a href="/rules-policies/current-rules-practice-procedure/federal-rules-civil-procedure">
                Federal Rules of Civil Procedure</a></li>
            <li><a href="/rules-policies/current-rules-practice-procedure/federal-rules-criminal-procedure">
                Federal Rules of Criminal Procedure</a></li>
        </ul>
    </div>
    </body>
    </html>
    """
