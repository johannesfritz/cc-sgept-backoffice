"""A standard deliverable invoice reaches the Amount column with one right tab, whatever the description length (JCC-9404)."""
from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.shared import Twips

RECIPIENT = {"company": "Test Client AG", "name": "Jane Doe", "street": "Street 1",
             "city": "8000 Zurich", "country": "Switzerland"}
LONG = "Policy intelligence dashboard licence, Q4 2026 XYZ"


def generate(generator, items, items_type, total):
    generator.generate_standard_invoice(
        invoice_number="99999", invoice_date="28 October 2026", currency="CHF", recipient=RECIPIENT,
        subject_line="Render check", intro_paragraph="A render check.", items=items,
        items_type=items_type, total=total, vat_note="No VAT is applied.", sync=False)
    (path,) = generator.OUTPUT_DIR.glob("*/*.docx")
    return Document(path).paragraphs


def right_tabs(paragraph):
    return [(stop.position, stop.alignment) for stop in paragraph.paragraph_format.tab_stops]


def test_header_items_and_total_share_one_right_tab(generator):
    assert len(LONG) == 50
    paragraphs = generate(generator, [{"description": "Short licence fee", "amount": 1200},
                                      {"description": LONG, "amount": 12000}], "deliverable", 13200)
    texts = [p.text for p in paragraphs]
    rows = {text.split("\t")[0]: paragraph for text, paragraph in zip(texts, paragraphs) if "\t" in text}
    expected = {"Description": "Amount (CHF)", "Short licence fee": "1,200.00", LONG: "12,000.00",
                "Invoice total:": "13,200.00"}
    for label, amount in expected.items():
        assert rows[label].text == f"{label}\t{amount}"
        assert right_tabs(rows[label]) == [(Twips(9026), WD_TAB_ALIGNMENT.RIGHT)]


def test_hours_invoice_keeps_its_columns(generator):
    paragraphs = generate(generator, [{"description": "J. Fritz", "hours": 45, "rate": 300, "total": 13500}],
                          "hours", 13500)
    texts = [p.text for p in paragraphs]
    assert "Description\t\t\tHours\tRate (CHF)\t\tTotal (CHF)" in texts
    assert "J. Fritz\t\t\t45\t300.00\t\t13,500.00" in texts
    assert "Invoice total:\t\t\t\t\t\t13,500.00" in texts
    assert all(right_tabs(p) == [] for p in paragraphs if p.text.startswith(("Description", "J. Fritz", "Invoice total")))
