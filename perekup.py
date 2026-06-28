import httpx
import asyncio

async def test():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    # Тест 1: прямой поиск
    url = "https://www.avito.ru/all?q=iPhone+17+Pro+Max+512"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, headers=headers, timeout=15)
        print(f"Статус: {resp.status_code}")
        print(f"URL после редиректа: {resp.url}")
        print(f"Длина ответа: {len(resp.text)}")
        print(f"Первые 500 символов: {resp.text[:500]}")
        print("---")
        
        # Ищем meta itemprop price
        import re
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        prices = soup.find_all("meta", itemprop="price")
        print(f"Найдено meta price: {len(prices)}")
        for p in prices[:3]:
            print(f"  Цена: {p.get('content')}")
        
        # Ищем span с ценой
        spans = soup.find_all("span", class_=re.compile(r"price"))
        print(f"Найдено span с price: {len(spans)}")
        for s in spans[:3]:
            print(f"  Текст: {s.get_text(strip=True)[:50]}")

asyncio.run(test())
