import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.goto('http://localhost:5177')
        await page.wait_for_timeout(3000)
        
        await page.mouse.click(500, 500) # Maybe spawn something?
        await page.wait_for_timeout(1000)
        await page.mouse.click(300, 300)
        await page.wait_for_timeout(1000)
        
        await page.screenshot(path="artifacts/screenshots/test_scr.png")
        await browser.close()

asyncio.run(main())
