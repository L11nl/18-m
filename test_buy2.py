import asyncio
import aiohttp
from dashboard.server import config

async def buy_number_debug(p_name):
    cfg = config["providers"].get(p_name, {})
    params = {"action": "getNumber", "api_key": cfg["key"], "service": cfg["service"], "country": cfg["country"]}
    servers = config.get("uotp_servers", []) if p_name == "UOTP" else [None]
    
    async with aiohttp.ClientSession() as session:
        for srv in servers:
            if srv: params["operator"] = srv
            print(f"[{p_name}] Requesting params: {params}")
            async with session.get(cfg["url"], params=params) as resp:
                text = (await resp.text()).strip()
                print(f"[{p_name}] Response: {text}")

async def main():
    await buy_number_debug("UOTP")
    await buy_number_debug("MeowSMS")

asyncio.run(main())
