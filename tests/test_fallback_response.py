import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_utils import build_fallback_response


def test_build_fallback_response_returns_text_for_arabic_and_english():
    ar = build_fallback_response('أريد وصفة حمص', 'ar')
    en = build_fallback_response('I want a hummus recipe', 'en')

    assert isinstance(ar, str) and len(ar) > 0
    assert isinstance(en, str) and len(en) > 0
    assert 'حمص' in ar or 'وصفة' in ar
    assert 'hummus' in en.lower() or 'recipe' in en.lower()
