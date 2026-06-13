import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.goto('http://localhost:5177')
        await page.wait_for_timeout(3000)
        
        # Click Red Knight card
        await page.mouse.click(125, 290)
        await page.wait_for_timeout(500)
        # Click on map top left
        await page.mouse.click(400, 200)
        await page.wait_for_timeout(500)
        
        # Click Blue Knight card
        await page.mouse.click(700, 290)
        await page.wait_for_timeout(500)
        # Click on map bottom right
        await page.mouse.click(600, 600)
        await page.wait_for_timeout(2000)
        
        await page.screenshot(path="test_knight.png")
        await browser.close()

asyncio.run(main())
