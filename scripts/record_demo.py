#!/usr/bin/env python3
"""Record a 10-second demo GIF of the dashboard using Playwright."""

import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import subprocess
import time

OUTPUT_DIR = Path(__file__).parent.parent / "assets"
VIDEO_PATH = OUTPUT_DIR / "demo_recording.webm"
GIF_PATH = OUTPUT_DIR / "dashboard_demo.gif"

async def record_demo():
    """Record the dashboard demo."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        # Launch browser with video recording
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(OUTPUT_DIR),
            record_video_size={"width": 1280, "height": 720}
        )

        page = await context.new_page()

        print("Loading dashboard...")
        await page.goto("http://localhost:8000/dashboard", wait_until="networkidle")
        await page.wait_for_timeout(1500)  # Let 3D scene initialize

        print("Recording demo interactions...")

        # 1. Show initial view with auto-rotating planets (2s)
        await page.wait_for_timeout(2000)

        # 2. Click on a planet to zoom in (2s)
        print("  - Clicking on a planet...")
        # Click near center-right where planets orbit
        await page.mouse.click(800, 400)
        await page.wait_for_timeout(2000)

        # 3. Click sun to zoom out (1s)
        print("  - Zooming out...")
        await page.mouse.click(640, 360)  # Center of viewport
        await page.wait_for_timeout(1500)

        # 4. Open chat panel and show it (2s)
        print("  - Opening chat panel...")
        chat_toggle = page.locator("#chat-console .toggle-btn").first
        if await chat_toggle.is_visible():
            await chat_toggle.click()
            await page.wait_for_timeout(1500)
            # Close it
            await chat_toggle.click()
            await page.wait_for_timeout(500)

        # 5. Pan around the scene (2s)
        print("  - Panning around...")
        await page.mouse.move(640, 360)
        await page.mouse.down()
        await page.mouse.move(500, 300, steps=20)
        await page.mouse.move(700, 400, steps=20)
        await page.mouse.up()
        await page.wait_for_timeout(1000)

        print("Recording complete!")

        # Close to finalize video
        await context.close()
        await browser.close()

        # Find the recorded video (Playwright names it with page ID)
        video_files = list(OUTPUT_DIR.glob("*.webm"))
        if video_files:
            latest_video = max(video_files, key=lambda f: f.stat().st_mtime)
            print(f"Video saved: {latest_video}")
            return latest_video

        return None


def convert_to_gif(video_path: Path, output_path: Path):
    """Convert video to optimized GIF using ffmpeg."""
    print(f"Converting {video_path} to GIF...")

    # Two-pass for better quality: generate palette, then use it
    palette_path = video_path.parent / "palette.png"

    # Generate palette
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", "fps=15,scale=640:-1:flags=lanczos,palettegen",
        str(palette_path)
    ], capture_output=True)

    # Use palette to create GIF
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path), "-i", str(palette_path),
        "-lavfi", "fps=15,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse",
        str(output_path)
    ], capture_output=True)

    # Cleanup palette
    palette_path.unlink(missing_ok=True)

    # Remove source video
    video_path.unlink(missing_ok=True)

    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"GIF created: {output_path} ({size_mb:.1f} MB)")
        return True
    return False


async def main():
    video_path = await record_demo()
    if video_path:
        convert_to_gif(video_path, GIF_PATH)
        print(f"\nDemo GIF ready: {GIF_PATH}")
    else:
        print("Failed to record video")


if __name__ == "__main__":
    asyncio.run(main())
