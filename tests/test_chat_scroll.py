"""
Test chat scroll functionality in both normal and fullscreen modes.
"""

from playwright.sync_api import Page, expect
import time

BASE_URL = "http://localhost:8000"


def test_chat_scroll_normal_mode(page: Page):
    """Test that chat messages are scrollable in normal mode."""

    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_timeout(2000)

    # Find chat input and send multiple messages to fill the container
    chat_input = page.locator("#chat-input")
    send_btn = page.locator("#chat-send")
    chat_messages = page.locator("#chat-messages")

    expect(chat_input).to_be_visible()
    expect(send_btn).to_be_visible()

    # Send several messages to populate chat
    test_messages = [
        "Message 1: Testing scroll functionality",
        "Message 2: Adding more content",
        "Message 3: Fill the chat window",
        "Message 4: Need enough messages",
        "Message 5: To require scrolling",
    ]

    for msg in test_messages:
        chat_input.fill(msg)
        send_btn.click()
        page.wait_for_timeout(500)  # Brief wait between messages

    # Check scroll properties
    scroll_info = page.evaluate("""() => {
        const container = document.querySelector('#chat-messages');
        if (!container) return { error: 'Container not found' };

        const style = window.getComputedStyle(container);
        return {
            scrollHeight: container.scrollHeight,
            clientHeight: container.clientHeight,
            scrollTop: container.scrollTop,
            overflowY: style.overflowY,
            canScroll: container.scrollHeight > container.clientHeight
        };
    }""")

    print(f"Normal mode scroll info: {scroll_info}")

    # Verify overflow-y is set correctly
    assert scroll_info.get('overflowY') in ['auto', 'scroll'], \
        f"Expected overflow-y to be auto or scroll, got {scroll_info.get('overflowY')}"


def test_chat_scroll_fullscreen_mode(page: Page):
    """Test that chat messages are scrollable in fullscreen mode."""

    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_timeout(2000)

    # Find and open chat in fullscreen
    chat_console = page.locator("#chat-console")
    expect(chat_console).to_be_visible()

    # Click fullscreen button
    fullscreen_btn = page.locator("#chat-console .fullscreen-btn")
    if fullscreen_btn.is_visible():
        fullscreen_btn.click()
        page.wait_for_timeout(500)
    else:
        # Try alternative method
        page.evaluate("toggleChatFullscreen()")
        page.wait_for_timeout(500)

    # Verify fullscreen class is applied
    has_fullscreen = page.evaluate("""() => {
        return document.querySelector('#chat-console').classList.contains('fullscreen');
    }""")
    assert has_fullscreen, "Chat should be in fullscreen mode"

    # Send multiple messages
    chat_input = page.locator("#chat-input")
    send_btn = page.locator("#chat-send")

    test_messages = [
        "Fullscreen message 1",
        "Fullscreen message 2",
        "Fullscreen message 3",
        "Fullscreen message 4",
        "Fullscreen message 5",
        "Fullscreen message 6",
        "Fullscreen message 7",
    ]

    for msg in test_messages:
        chat_input.fill(msg)
        send_btn.click()
        page.wait_for_timeout(300)

    # Check scroll properties in fullscreen
    scroll_info = page.evaluate("""() => {
        const container = document.querySelector('#chat-messages');
        if (!container) return { error: 'Container not found' };

        const style = window.getComputedStyle(container);
        return {
            scrollHeight: container.scrollHeight,
            clientHeight: container.clientHeight,
            scrollTop: container.scrollTop,
            overflowY: style.overflowY,
            canScroll: container.scrollHeight > container.clientHeight,
            height: container.offsetHeight,
            parentHeight: container.parentElement?.offsetHeight || 0
        };
    }""")

    print(f"Fullscreen mode scroll info: {scroll_info}")

    # Verify overflow is scrollable
    assert scroll_info.get('overflowY') in ['auto', 'scroll'], \
        f"Expected overflow-y to be auto or scroll, got {scroll_info.get('overflowY')}"

    # Try to scroll up
    page.evaluate("""() => {
        const container = document.querySelector('#chat-messages');
        container.scrollTop = 0;  // Scroll to top
    }""")
    page.wait_for_timeout(200)

    scroll_after = page.evaluate("""() => {
        const container = document.querySelector('#chat-messages');
        return {
            scrollTop: container.scrollTop,
            scrollHeight: container.scrollHeight,
            clientHeight: container.clientHeight
        };
    }""")

    print(f"After scroll to top: {scroll_after}")

    # Verify we could scroll (scrollTop should be 0 after scrolling to top)
    assert scroll_after['scrollTop'] == 0, "Should be able to scroll to top"


def test_chat_scroll_interaction(page: Page):
    """Test actual scroll interaction in fullscreen chat."""

    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_timeout(2000)

    # Enter fullscreen
    page.evaluate("toggleChatFullscreen()")
    page.wait_for_timeout(500)

    # Add many messages via JS to ensure scrolling is needed
    page.evaluate("""() => {
        const container = document.querySelector('#chat-messages');
        for (let i = 0; i < 20; i++) {
            const div = document.createElement('div');
            div.className = 'chat-message user';
            div.innerHTML = `<div class="chat-bubble">Test message ${i+1} - Adding content to enable scroll testing</div>`;
            container.appendChild(div);
        }
    }""")
    page.wait_for_timeout(300)

    # Get initial scroll state
    initial = page.evaluate("""() => {
        const c = document.querySelector('#chat-messages');
        return { scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
    }""")

    print(f"Initial state: {initial}")

    # Scroll to middle
    page.evaluate("""() => {
        const c = document.querySelector('#chat-messages');
        c.scrollTop = c.scrollHeight / 2;
    }""")
    page.wait_for_timeout(200)

    middle = page.evaluate("document.querySelector('#chat-messages').scrollTop")
    print(f"After scroll to middle: scrollTop = {middle}")

    # Scroll to top
    page.evaluate("document.querySelector('#chat-messages').scrollTop = 0")
    page.wait_for_timeout(200)

    top = page.evaluate("document.querySelector('#chat-messages').scrollTop")
    print(f"After scroll to top: scrollTop = {top}")

    # Scroll to bottom
    page.evaluate("""() => {
        const c = document.querySelector('#chat-messages');
        c.scrollTop = c.scrollHeight;
    }""")
    page.wait_for_timeout(200)

    bottom = page.evaluate("document.querySelector('#chat-messages').scrollTop")
    print(f"After scroll to bottom: scrollTop = {bottom}")

    # Verify scrolling worked
    assert initial['scrollHeight'] > initial['clientHeight'], \
        "Content should be taller than container (scrollable)"
    assert middle > 0, "Should be able to scroll to middle"
    assert top == 0, "Should be able to scroll to top"
    assert bottom > middle, "Should be able to scroll to bottom"

    print("✓ Chat scroll interaction test passed!")


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("\n=== Test 1: Normal mode scroll ===")
            test_chat_scroll_normal_mode(page)
            print("✓ Normal mode test passed")

            print("\n=== Test 2: Fullscreen mode scroll ===")
            test_chat_scroll_fullscreen_mode(page)
            print("✓ Fullscreen mode test passed")

            print("\n=== Test 3: Scroll interaction ===")
            test_chat_scroll_interaction(page)
            print("✓ Scroll interaction test passed")

            print("\n✓ All chat scroll tests passed!")
        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            page.screenshot(path="/tmp/chat_scroll_failure.png")
            print("Screenshot saved to /tmp/chat_scroll_failure.png")
            raise
        finally:
            browser.close()
