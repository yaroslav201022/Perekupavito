import httpx
import asyncio

async def test():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    tests = [
        ("Поиск WB", "https://search.wb.ru/exactmatch/ru/common/v9/search?ab_testing=false&appType=1&curr=rub&dest=-1257786&query=924286080&resultset=catalog&sort=popular&spp=30"),
        ("Basket 01", "https://basket-01.wb.ru/vol924/part92428/924286080/info/ru/card.json"),
        ("Basket 02", "https://basket-02.wb.ru/vol924/part92428/924286080/info/ru/card.json"),
        ("Карточка WB", "https://www.wildberries.ru/catalog/924286080/detail.aspx"),
        ("Яндекс", "https://ya.ru"),
        ("Google", "https://google.com"),
    ]
    
    async with httpx.AsyncClient() as client:
        for name, url in tests:
            try:
                resp = await client.get(url, headers=headers, timeout=10)
                print(f"✅ {name}: статус {resp.status_code}, длина ответа {len(resp.text)}")
            except Exception as e:
                print(f"❌ {name}: ОШИБКА — {str(e)[:100]}")

asyncio.run(test())
