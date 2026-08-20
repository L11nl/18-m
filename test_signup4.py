import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        page.on("response", lambda response: print(f"Response: {response.url} - {response.status}"))
        
        print("Navigating to Omkar signup...")
        await page.goto("https://www.omkar.cloud/auth/sign-up", wait_until="networkidle")
        await asyncio.sleep(2) # Extra wait for hydration
        
        print("Filling form...")
        await page.locator('input[name="name"]').press_sequentially("Test User", delay=50)
        await page.locator('input[type="email"]').press_sequentially("test_omkar_9999@outlook.com", delay=50)
        await page.locator('input[type="password"]').press_sequentially("Testing123!", delay=50)
        
        print("Submitting...")
        # Ensure we click exactly on the button, force=True ignores covering elements
        await page.locator('button:has-text("Submit")').click(force=True)
        
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass
            
        print(f"Final URL: {page.url}")
        
        content = await page.content()
        if "Verify your email" in content or "Sent" in content or "Check" in content:
            print("Looks like submission worked!")
        else:
            print("Did not find verification message.")
            
        await context.close()

asyncio.run(main())
