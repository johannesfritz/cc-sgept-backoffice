"""Every NIPO tier writes the requested subscription period into the body text.

The academic library template holds its period inside one longer run, which
the span replacement alone missed, so invoice 26040 first came out with the
template's "January 2026 to December 2026".
"""
import pytest
from docx import Document

from conftest import nipo_spec


@pytest.mark.parametrize("tier", ["regular", "academic_library"])
def test_body_carries_requested_period(generator, tier):
    spec = dict(nipo_spec("26901"), tier=tier, subscription_period="November 2026 - October 2027")
    generator.generate_from_spec(spec)
    (docx_path,) = generator.OUTPUT_DIR.glob("*/*.docx")
    body = "\n".join(p.text for p in Document(docx_path).paragraphs)
    assert "November 2026" in body
    assert "October 2027" in body
    assert "January 2026" not in body
    assert "December 2026" not in body
