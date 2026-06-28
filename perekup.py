import httpx
import asyncio

async def test():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    urls = [
        "https://m.avito.ru/api/11/items?query=iPhone+17+Pro+Max&limit=3",
        "https://api.avito.ru/core/v1/items?query=iPhone&limit=3",
        "https://www.avito.ru/web/1/items?query=iPhone&limit=3",
    ]
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url, headers=headers, timeout=10)
                print(f"URL: {url}")
                print(f"Статус: {resp.status_code}")
                print(f"Длина: {len(resp.text)}")
                print(f"Ответ: {resp.text[:500]}")
                print("---")
            except Exception as e:
                print(f"URL: {url}")
                print(f"Ошибка: {e}")
                print("---")

asyncio.run(test())
