import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.goto('http://localhost:5177')
        await page.wait_for_timeout(3000)
        
        # Inject Knight
        await page.evaluate("""
            const e = window.engine.game.spawnEntity('knight', {x: 10, y: 15}, 'red');
            e.pos.x = 10;
            e.pos.y = 15;
        """)
        await page.wait_for_timeout(1000)
        
        await page.screenshot(path="artifacts/screenshots/test_spawn.png")
        await browser.close()

asyncio.run(main())
