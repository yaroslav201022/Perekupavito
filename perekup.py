import httpx
import asyncio

async def test():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    url = "https://search.wb.ru/exactmatch/ru/common/v9/search?ab_testing=false&appType=1&curr=rub&dest=-1257786&query=наушники+беспроводные&resultset=catalog&sort=popular&spp=5"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=15)
        print(f"Статус: {resp.status_code}")
        print(f"Ответ: {resp.text[:2000]}")

asyncio.run(test())
