"""
Test chat with Dexter integration using Playwright.
"""

from playwright.sync_api import Page, expect
import time

BASE_URL = "http://localhost:8000"


def test_chat_with_dexter(page: Page):
    """Test that chat uses Dexter for options queries."""

    # Go to dashboard
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_timeout(3000)

    # Find chat input
    chat_input = page.locator("#chat-input")
    expect(chat_input).to_be_visible()

    # Type question
    chat_input.fill("show tsla options 30 days out")

    # Find and click send button
    send_btn = page.locator("#chat-send")
    expect(send_btn).to_be_visible()
    send_btn.click()

    # Wait for response (Dexter can take a while)
    print("Waiting for Dexter response...")
    page.wait_for_timeout(45000)

    # Get the chat container content
    chat_container = page.locator("#chat-messages")
    full_text = chat_container.inner_text()

    print("\n" + "="*60)
    print("FULL CHAT RESPONSE:")
    print("="*60)
    print(full_text)
    print("="*60)

    # Check for Dexter response indicators
    has_research_query = "[RESEARCH_QUERY" in full_text
    has_options_data = any([
        "strike" in full_text.lower(),
        "premium" in full_text.lower(),
        "$4" in full_text or "$5" in full_text or "$3" in full_text,  # Premium values
    ])

    # Look for specific error messages
    dexter_not_available = "dexter is not available" in full_text.lower()
    research_failed = "research query failed" in full_text.lower()

    print(f"\nUsed RESEARCH_QUERY: {has_research_query}")
    print(f"Has options data: {has_options_data}")
    print(f"Dexter not available error: {dexter_not_available}")
    print(f"Research failed error: {research_failed}")

    if dexter_not_available:
        raise AssertionError("Dexter is not available!")
    if research_failed:
        raise AssertionError("Research query failed!")

    assert has_research_query, "Should use RESEARCH_QUERY for options questions"


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            test_chat_with_dexter(page)
            print("\n✓ Test passed!")
        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            page.screenshot(path="/tmp/chat_test_failure.png")
            print("Screenshot saved to /tmp/chat_test_failure.png")
            raise
        finally:
            browser.close()
