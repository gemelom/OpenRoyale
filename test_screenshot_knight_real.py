import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.goto('http://localhost:5177')
        await page.wait_for_timeout(3000)
        
        # Click Knight (Red Team) -> let's use exact text selector
        await page.click("text=Knight", strict=False)
        await page.wait_for_timeout(500)
        
        # Click on map
        await page.mouse.click(400, 200)
        await page.wait_for_timeout(1000)
        
        await page.screenshot(path="test_knight_real.png")
        await browser.close()

asyncio.run(main())
