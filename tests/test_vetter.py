from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage
from vc_vetter.config import Settings
from vc_vetter.vetter import VCVetter, VettingDecision

def test_vetter_analyze_fit_success():
    """Verifies that VCVetter correctly formats instructions, calls LLM, and parses structured output."""
    mock_llm = MagicMock()
    
    # Mock LLM return value. The prompt expects a JSON-formatted string matching the schema.
    mock_llm_response = AIMessage(content='{"is_fit": true, "reasoning": "The fund focuses on Seed-stage B2B software which is a perfect match."}')
    mock_llm.return_value = mock_llm_response
    mock_llm.invoke.return_value = mock_llm_response
    
    vetter = VCVetter(llm=mock_llm)
    
    result = vetter.analyze_fit(
        website_text="We invest in seed stage B2B SaaS companies.",
        startup_info="- Product: Sales SaaS\n- Fundraising Round: Seed\n- Target Market: B2B"
    )
    
    # Verify that the parsed output conforms to the Pydantic schema
    assert isinstance(result, VettingDecision)
    assert result.is_fit is True
    assert result.reasoning == "The fund focuses on Seed-stage B2B software which is a perfect match."
    
    # Verify LLM was invoked
    assert mock_llm.called

def test_vetter_analyze_fit_empty_website():
    """Verifies that empty website content is rejected immediately without hitting the LLM."""
    vetter = VCVetter()
    result = vetter.analyze_fit("   ", "Startup profile info")
    
    assert isinstance(result, VettingDecision)
    assert result.is_fit is False
    assert "Could not scrape" in result.reasoning

def test_vetter_analyze_fit_llm_error():
    """Verifies that VCVetter catches LLM invocation failures gracefully and returns a negative decision."""
    mock_llm = MagicMock()
    mock_llm.side_effect = Exception("Ollama server not running")
    mock_llm.invoke.side_effect = Exception("Ollama server not running")
    
    vetter = VCVetter(llm=mock_llm)
    result = vetter.analyze_fit(
        website_text="Any text",
        startup_info="Any startup info"
    )
    
    assert isinstance(result, VettingDecision)
    assert result.is_fit is False
    assert "LLM analysis failed" in result.reasoning
