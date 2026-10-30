from lecture_prep.compare import blind_page
from lecture_prep.db.models import SummaryKind


def test_blind_page_hides_which_model_wrote_which_until_the_end():
    versions = {SummaryKind.PREP: {"Claude": "### מקלוד", "Gemini": "### מג'מיני", "Sonnet": "### מסונט"}}

    page = blind_page("תכנות מערכות", 5, versions)

    body, reveal = page.split("<details>")
    assert "גרסה A" in body and "גרסה B" in body and "גרסה C" in body
    assert "Claude" not in body and "Gemini" not in body and "Sonnet" not in body
    assert "מקלוד" in body and "מג" in body
    assert "Claude" in reveal and "Gemini" in reveal and "Sonnet" in reveal
