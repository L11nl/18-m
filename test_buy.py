import asyncio
import aiohttp
import json

from dashboard.server import buy_number, state, config

async def main():
    state.http_session = aiohttp.ClientSession()
    print("Testing UOTP:")
    res1 = await buy_number("UOTP")
    print(res1)
    print("Testing MeowSMS:")
    res2 = await buy_number("MeowSMS")
    print(res2)
    await state.http_session.close()

asyncio.run(main())
