"""Generate the fictional sample PDFs used by the demo (already committed; rerun to regenerate)."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ROOT = Path(__file__).resolve().parent.parent / "data"
styles = getSampleStyleSheet()

DOCS = {
    "docs/acme/Acme_Office_Lease.pdf": [
        ("Office Lease Agreement - Acme Logistics Pvt Ltd", [
            "This lease is between Brightstone Properties (Landlord) and Acme Logistics Pvt Ltd (Tenant) for Unit 402, Orion Business Park, Bengaluru.",
            "The lease term is 36 months, starting 1 April 2026 and ending 31 March 2029.",
        ]),
        ("Rent and Deposit", [
            "Monthly rent is INR 2,40,000, payable on or before the 5th day of each month.",
            "A late fee of 2% of the monthly rent applies to any payment received after the 10th day of the month.",
            "The security deposit is INR 14,40,000 (six months of rent), refundable within 45 days of the tenant vacating, less any deductions for damage.",
        ]),
        ("Maintenance and Termination", [
            "Rent escalates by 5% at the start of each lease year.",
            "Either party may terminate the lease with 3 months' written notice after a lock-in period of 12 months.",
            "The landlord is responsible for structural repairs; the tenant is responsible for interior maintenance and the air-conditioning service contract.",
        ]),
    ],
    "docs/acme/Acme_Fleet_Insurance.pdf": [
        ("Fleet Insurance Policy - Acme Logistics Pvt Ltd", [
            "Policy number FLT-88213 is issued by Suraksha General Insurance and covers 42 commercial vehicles.",
            "The policy period runs from 1 July 2026 to 30 June 2027.",
        ]),
        ("Coverage and Claims", [
            "Own-damage cover has a deductible of INR 25,000 per claim.",
            "Third-party liability is covered up to INR 7,50,000 per incident for property damage.",
            "Claims must be reported within 48 hours of an incident by calling the claims desk or emailing the policy number with photographs.",
            "Damage caused by driving under the influence or by an unlicensed driver is excluded from cover.",
        ]),
    ],
    "docs/globex/Globex_Employee_Handbook.pdf": [
        ("Employee Handbook - Globex Retail", [
            "Employees receive 18 days of paid annual leave per calendar year.",
            "Up to 6 unused leave days may be carried over to the next year.",
        ]),
        ("Working Hours and Expenses", [
            "Standard working hours are 9:30 am to 6:30 pm, Monday to Friday.",
            "Travel expenses must be submitted within 30 days with original receipts; claims above INR 10,000 need manager approval.",
        ]),
    ],
    # Held back on purpose: never ingested. Questions about it must be refused.
    "holdout/acme/Acme_Warehouse_Warranty.pdf": [
        ("Racking Warranty - Acme Logistics", [
            "The warehouse racking system installed by SteelGrid is under warranty for 7 years.",
            "The warranty covers manufacturing defects but not damage from forklift impact.",
        ]),
    ],
}

for rel, sections in DOCS.items():
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    story = []
    for i, (heading, paras) in enumerate(sections):
        if i:
            story.append(PageBreak())  # one section per page so page citations are meaningful
        story.append(Paragraph(heading, styles["Heading1"]))
        for p in paras:
            story.append(Paragraph(p, styles["BodyText"]))
            story.append(Spacer(1, 8))
    doc.build(story)
    print("wrote", path)
