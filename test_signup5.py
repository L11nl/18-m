import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        await page.goto("https://www.omkar.cloud/auth/sign-up", wait_until="networkidle")
        
        await page.locator('input[name="name"]').fill("Test User")
        await page.locator('input[type="email"]').fill("test_omkar_9999@outlook.com")
        await page.locator('input[type="password"]').fill("Testing123!")
        
        await page.locator('button[type="submit"]').click()
        await asyncio.sleep(2)
        
        # Check all text on the page to see if an error message like "email already taken" or "invalid password" appeared
        body_text = await page.evaluate("document.body.innerText")
        print("--- BODY TEXT AFTER SUBMIT ---")
        print(body_text)
        
        await context.close()

asyncio.run(main())
