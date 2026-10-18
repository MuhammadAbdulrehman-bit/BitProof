import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#555555"))
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 36, page_text)
        self.drawString(54, 36, "RFP # NIT-IT-2026-08 | National Cloud Identity Platform | Single Stage Two Envelope")
        self.setStrokeColor(colors.HexColor("#cccccc"))
        self.setLineWidth(0.5)
        self.line(54, 48, 612 - 54, 48)
        self.restoreState()


def build_pdf(filename="data/sample_rfp.pdf"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A365D"),
        alignment=1, # Center
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2B6CB0"),
        alignment=1,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SubSectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=1
    )

    table_body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#2D3748")
    )

    story = []

    # Title Block
    story.append(Paragraph("GOVERNMENT OF PAKISTAN", subtitle_style))
    story.append(Paragraph("MINISTRY OF INFORMATION TECHNOLOGY &amp; TELECOMMUNICATION", ParagraphStyle('MinTitle', parent=subtitle_style, fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor("#1A365D"))))
    story.append(Paragraph("REQUEST FOR PROPOSAL (RFP)", title_style))
    story.append(Paragraph("Procurement of National Single-Sign-On &amp; Cloud Identity Platform<br/><b>Tender Reference No.: NIT-IT-2026-08 | PPRA Rule 36(b) Single Stage Two Envelope</b>", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1A365D"), spaceAfter=12))

    # Section 1
    story.append(Paragraph("SECTION 1: INVITATION FOR BIDS &amp; BACKGROUND", h1_style))
    story.append(Paragraph("1.1 The Ministry of Information Technology and Telecommunication (MoITT), Government of Pakistan invites sealed bids from eligible, reputed technology firms registered with relevant tax authorities for the deployment and management of a National Single-Sign-On and Cloud Identity Platform.", body_style))
    story.append(Paragraph("1.2 The primary objective of this project is to centralize identity verification, access management, and multi-factor authentication across federal and provincial citizen digital service portals.", body_style))
    story.append(Paragraph("1.3 Procurement shall be conducted strictly in accordance with Public Procurement Rules 2026 and e-PADS Standard Bidding Regulations through Single Stage Two Envelope Bidding Procedure.", body_style))
    story.append(Paragraph("1.4 The procuring agency reserves the right to annul the procurement process at any stage prior to acceptance of bid in accordance with Rule 33 of Public Procurement Rules.", body_style))
    story.append(Paragraph("1.5 The procuring agency will provide cloud hosting infrastructure at the National Data Center for deployment.", body_style))

    # Section 2
    story.append(Paragraph("SECTION 2: MANDATORY ELIGIBILITY CRITERIA (KNOCKOUT)", h1_style))
    story.append(Paragraph("Bidders must meet all of the following preliminary mandatory qualification criteria. Proposals failing to satisfy any single criterion shall be declared non-responsive and disqualified without technical evaluation:", body_style))
    
    eligibility_items = [
        "2.1 The bidder must be an active taxpayer listed on the Federal Board of Revenue (FBR) Active Taxpayers List (ATL) for Income Tax and Sales Tax on the date of bid submission.",
        "2.2 The bidder must possess a valid National Tax Number (NTN) and Sales Tax Registration Number (STRN).",
        "2.3 The bidder must have at least five (05) years of verifiable corporate operational experience in Pakistan in enterprise software development or identity access management.",
        "2.4 The bidder must submit an original affidavit on non-judicial stamp paper stating that the firm is not blacklisted or debarred by any government department, PPRA, or international agency.",
        "2.5 The bidder must demonstrate an average annual financial turnover of at least PKR 150 Million over the last three (03) audited financial fiscal years.",
        "2.6 The bidder must submit the original Bid Securing Declaration as per Form TECH-4 in the technical proposal envelope."
    ]
    for item in eligibility_items:
        story.append(Paragraph(f"• {item}", bullet_style))

    # Section 3
    story.append(Paragraph("SECTION 3: SCOPE OF SERVICES &amp; TECHNICAL REQUIREMENTS", h1_style))
    story.append(Paragraph("The selected solution provider will execute the complete scope of supply, integration, customization, and warranty support according to the following specifications:", body_style))
    
    tech_items = [
        "3.1 The solution shall support OpenID Connect (OIDC), OAuth 2.0, and SAML 2.0 federation protocols out of the box.",
        "3.2 The system must support citizen authentication via Pakistani National ID (CNIC) and integration with NADRA Pak-Identity verification APIs.",
        "3.3 All citizen profile data and audit records must reside exclusively within servers located physically inside Pakistan (local data residency requirement).",
        "3.4 The vendor shall provide high-availability architecture guaranteeing a minimum system uptime SLA of 99.9% on a 24x7x365 basis.",
        "3.5 The system will support automated failover to the secondary disaster recovery site with an RPO under 5 minutes and RTO under 15 minutes.",
        "3.6 The vendor must supply comprehensive RESTful APIs with OpenAPI 3.0 specification for third-party agency integration.",
        "3.7 The platform should preferably support passwordless authentication mechanisms including WebAuthn and FIDO2 standards.",
        "3.8 The vendor will provide three (03) years of comprehensive on-site warranty and software maintenance support starting from the Date of Operational Acceptance.",
        "3.9 The vendor shall provide certified technical training for twelve (12) IT staff members of the procuring agency prior to system go-live.",
        "3.10 Bidders should submit an illustrated project deployment organogram and risk mitigation matrix."
    ]
    for item in tech_items:
        story.append(Paragraph(f"• {item}", bullet_style))

    # Section 4
    story.append(PageBreak())
    story.append(Paragraph("SECTION 4: TECHNICAL EVALUATION CRITERIA &amp; SCORING (QCBS 70/30)", h1_style))
    story.append(Paragraph("4.1 Bids will be evaluated using Quality and Cost Based Selection (QCBS) mechanism with 70% weight for Technical Proposal and 30% weight for Financial Proposal.", body_style))
    story.append(Paragraph("4.2 The minimum qualifying technical score is 70 marks out of 100. Any bid scoring less than 70 marks shall be rejected as technically non-responsive, and its financial proposal will be returned unopened.", body_style))
    
    # Table of scoring criteria
    table_data = [
        [
            Paragraph("<b>Sr.</b>", table_header_style),
            Paragraph("<b>Evaluation Parameter</b>", table_header_style),
            Paragraph("<b>Max Marks</b>", table_header_style),
            Paragraph("<b>Scoring Basis</b>", table_header_style)
        ],
        [
            Paragraph("1", table_body_style),
            Paragraph("<b>Firm Corporate Profile &amp; Experience</b><br/>Verifiable experience in identity/cloud projects", table_body_style),
            Paragraph("<b>25</b>", table_body_style),
            Paragraph("5 projects = 25 marks; 3-4 projects = 18 marks; 1-2 projects = 10 marks; 0 projects = 0 marks.", table_body_style)
        ],
        [
            Paragraph("2", table_body_style),
            Paragraph("<b>Technical Architecture &amp; Methodology</b><br/>Design, scalability, security architecture, NADRA compliance", table_body_style),
            Paragraph("<b>30</b>", table_body_style),
            Paragraph("Architectural soundness (15 marks), Security controls &amp; OWASP compliance (10 marks), Work plan (5 marks).", table_body_style)
        ],
        [
            Paragraph("3", table_body_style),
            Paragraph("<b>Key Human Resources</b><br/>Qualifications and experience of proposed team", table_body_style),
            Paragraph("<b>25</b>", table_body_style),
            Paragraph("Lead Solution Architect (10 marks), Security Specialist (8 marks), DevOps/Cloud Engineer (7 marks).", table_body_style)
        ],
        [
            Paragraph("4", table_body_style),
            Paragraph("<b>Live System Demonstration</b><br/>Functional walkthrough of identity lifecycle &amp; MFA", table_body_style),
            Paragraph("<b>20</b>", table_body_style),
            Paragraph("Live demonstration of OIDC flow (10 marks), Admin portal &amp; audit logging (10 marks).", table_body_style)
        ],
        [
            Paragraph("<b>Total</b>", table_header_style),
            Paragraph("<b>Total Technical Score</b>", table_header_style),
            Paragraph("<b>100</b>", table_header_style),
            Paragraph("<b>Passing threshold: 70 Marks</b>", table_header_style)
        ]
    ]

    t = Table(table_data, colWidths=[28, 160, 56, 260])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#2B6CB0")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Section 5
    story.append(Paragraph("SECTION 5: SUBMISSION, BID SECURITY &amp; COMMERCIAL TERMS", h1_style))
    story.append(Paragraph("5.1 Bids must be submitted electronically via the e-PADS portal (eprocure.gov.pk) no later than 28 October 2026 at 11:00 AM PKT.", body_style))
    story.append(Paragraph("5.2 Late bids submitted after the stipulated deadline shall not be entertained and will be automatically locked out by e-PADS.", body_style))
    story.append(Paragraph("5.3 The bidder must furnish a Bid Security equal to two percent (2%) of the total bid price in the form of a Pay Order or Bank Guarantee issued by a scheduled Pakistani bank.", body_style))
    story.append(Paragraph("5.4 The original physical Bid Security instrument must be delivered to the MoITT procurement office before the bid submission deadline. Any bid submitted without bid security shall be summarily rejected.", body_style))
    story.append(Paragraph("5.5 Bids shall remain valid for a period of ninety (90) calendar days from the date of technical bid opening.", body_style))
    story.append(Paragraph("5.6 The financial proposal must state prices in Pakistani Rupees (PKR) inclusive of all federal and provincial taxes, levies, and duties.", body_style))
    story.append(Paragraph("5.7 Any conditional, ambiguous, or alternative financial bid shall be rejected as non-responsive.", body_style))
    story.append(Paragraph("5.8 Payment terms shall be milestone-based: 20% on Requirement Sign-off, 40% on Pilot Deployment, 30% on Final Acceptance, and 10% retention upon completion of the warranty period.", body_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")

if __name__ == "__main__":
    build_pdf("data/sample_rfp.pdf")
