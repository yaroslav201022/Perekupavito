import httpx
import asyncio
import re
import json

async def test():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    url = "https://www.avito.ru/all?q=iPhone+17+Pro+Max+512"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, headers=headers, timeout=15)
        
        # Ищем все JSON-объекты в script-тегах
        script_tags = re.findall(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        print(f"Всего script-тегов: {len(script_tags)}")
        
        for i, script in enumerate(script_tags):
            # Ищем window.__INITIAL_STATE__ или похожие
            if 'window.__' in script[:200] or 'initial' in script[:200].lower() or 'state' in script[:200].lower():
                print(f"\nScript #{i}: первые 600 символов:")
                print(script[:600])
                print("...")
            
            # Ищем JSON с ценами
            if '"price"' in script.lower() and len(script) < 5000:
                print(f"\nScript #{i} (с price, короткий):")
                print(script[:800])

asyncio.run(test())
