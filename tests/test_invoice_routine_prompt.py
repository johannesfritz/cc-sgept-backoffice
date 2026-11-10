"""The server invoice routine sends the CEO nothing (decision 589, JCC-10224, row E22).

The forwards to the fiduciary carry no copy, and the day-14 escalation is a file
in the month folder, not a Slack message.
"""
from pathlib import Path

PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "invoice-routine-server.md"


def test_forwards_carry_no_copy():
    assert '"cc"' not in PROMPT.read_text(encoding="utf-8")


def test_escalation_is_a_file_not_a_slack_message():
    text = PROMPT.read_text(encoding="utf-8")
    assert "slack_send_message" not in text
    section = text[text.index("## SECTION G"):text.index("## STEP 8")]
    assert "Send no Slack message and no email to the CEO." in section
    assert "Second reminders sent to:" in section
