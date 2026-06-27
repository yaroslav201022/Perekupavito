import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# ================== ТОКЕН ==================
BOT_TOKEN = "8879391155:AAFy2q-8kMCxfEnl_1D6I1AqP5Ug9VfP73w"

# ================== ЛОГИ ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== ИНИЦИАЛИЗАЦИЯ ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== ПАРСЕР WILDBERRIES ==================
async def parse_wb(url: str) -> dict:
    """Парсит товар Wildberries через HTML страницы"""
    article_match = re.search(r'(\d{7,15})', url)
    if not article_match:
        return {"error": "Не удалось найти артикул в ссылке"}

    article = article_match.group(1)
    product_url = f"https://www.wildberries.ru/catalog/{article}/detail.aspx"
    
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Referer": "https://www.wildberries.ru/",
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            resp = await client.get(product_url, headers=headers, timeout=20)
            
            if resp.status_code != 200:
                return {"error": f"WB вернул статус {resp.status_code}"}

            html = resp.text
            
            # Ищем JSON с данными товара в HTML
            # Вариант 1: window.__INITIAL_STATE__
            state_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
            if state_match:
                import json
                try:
                    state = json.loads(state_match.group(1))
                    product = state.get("product", {}).get("productCard", {}).get("data", {})
                    
                    if product:
                        name = product.get("goodsName") or product.get("name", "Без названия")
                        brand = product.get("brand", "")
                        price = product.get("salePriceU", product.get("priceU", 0)) / 100
                        rating = product.get("reviewRating", 0)
                        reviews = product.get("feedbacks", 0)
                        
                        return {
                            "name": f"{brand} {name}".strip(),
                            "price": price,
                            "rating": rating,
                            "reviews": reviews,
                            "article": article
                        }
                except:
                    pass
            
            # Вариант 2: SSG-данные
            ssg_match = re.search(r'<script id="ssr-data">(.*?)</script>', html, re.DOTALL)
            if ssg_match:
                import json
                try:
                    data = json.loads(ssg_match.group(1))
                    # Ищем в разных местах
                    pass
                except:
                    pass
            
            # Вариант 3: Парсим HTML напрямую
            soup = BeautifulSoup(html, "html.parser")
            
            # Название
            name_tag = soup.find("h1")
            name = name_tag.get_text(strip=True) if name_tag else "Без названия"
            
            # Бренд
            brand_tag = soup.find("span", {"data-link": re.compile(r"brand")})
            brand = brand_tag.get_text(strip=True) if brand_tag else ""
            
            # Цена
            price_tag = soup.find("ins", class_="price-block__final-price")
            if not price_tag:
                price_tag = soup.find("span", class_=re.compile(r"price"))
            
            price = 0
            if price_tag:
                price_text = price_tag.get_text(strip=True).replace("\xa0", "").replace(" ", "")
                price_match = re.search(r'(\d+)', price_text)
                if price_match:
                    price = int(price_match.group(1))
            
            # Рейтинг и отзывы
            rating_tag = soup.find("span", {"data-link": re.compile(r"rating")})
            rating = 0
            reviews = 0
            if rating_tag:
                rating_text = rating_tag.get_text(strip=True)
                rating_match = re.search(r'([\d.]+)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))
            
            reviews_tag = soup.find("span", class_=re.compile(r"count"))
            if not reviews_tag:
                reviews_tag = soup.find("span", string=re.compile(r"отзыв"))
            if reviews_tag:
                rev_text = reviews_tag.get_text(strip=True)
                rev_match = re.search(r'(\d+)', rev_text)
                if rev_match:
                    reviews = int(rev_match.group(1))
            
            if price == 0:
                return {"error": "Не удалось найти цену. Возможно, товар недоступен."}
            
            return {
                "name": f"{brand} {name}".strip(),
                "price": price,
                "rating": rating,
                "reviews": reviews,
                "article": article
            }
            
        except Exception as e:
            return {"error": f"Ошибка парсинга WB: {str(e)}"}

# ================== ПАРСЕР АВИТО ==================
async def parse_avito(query: str) -> dict:
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.8",
    }

    short_query = " ".join(query.split()[:4])
    search_url = f"https://www.avito.ru/all?q={short_query}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(search_url, headers=headers, timeout=15)

            if resp.status_code != 200:
                return {"error": f"Авито ответил {resp.status_code}", "prices": [], "avg": 0, "median": 0, "count": 0}

            soup = BeautifulSoup(resp.text, "html.parser")
            price_items = soup.find_all("meta", itemprop="price")
            prices = []
            for item in price_items:
                content = item.get("content")
                if content:
                    try:
                        price = float(content)
                        if price > 0:
                            prices.append(price)
                    except:
                        continue

            if not prices:
                price_blocks = soup.find_all("span", class_=re.compile(r".*price.*"))
                for block in price_blocks:
                    text = block.get_text(strip=True)
                    numbers = re.findall(r'[\d\s]+', text)
                    if numbers:
                        num = numbers[0].replace(" ", "").replace("\xa0", "")
                        try:
                            price = float(num)
                            if 100 < price < 10_000_000:
                                prices.append(price)
                        except:
                            continue

            if not prices:
                return {"error": "Цены не найдены. Возможна капча.", "prices": [], "avg": 0, "median": 0, "count": 0}

            avg = sum(prices) / len(prices)
            sorted_prices = sorted(prices)
            median = sorted_prices[len(sorted_prices) // 2]

            return {
                "prices": sorted_prices[:10],
                "avg": round(avg, 2),
                "median": round(median, 2),
                "count": len(prices)
            }
        except Exception as e:
            return {"error": f"Ошибка Авито: {str(e)}", "prices": [], "avg": 0, "median": 0, "count": 0}

# ================== ФОРМАТИРОВАНИЕ ОТВЕТА ==================
def format_analysis(wb_data: dict, avito_data: dict) -> str:
    if "error" in wb_data:
        return f"❌ Ошибка Wildberries: {wb_data['error']}"

    if "error" in avito_data:
        price_wb = wb_data.get("price", 0)
        return (
            f"📦 *{wb_data.get('name', 'Товар')}*\n\n"
            f"💰 Цена на WB: *{int(price_wb):,} ₽*\n"
            f"⭐ Рейтинг: {wb_data.get('rating', '?')} | Отзывов: {wb_data.get('reviews', '?')}\n\n"
            f"⚠️ Авито: {avito_data.get('error', 'Нет данных')}"
        )

    price_wb = wb_data.get("price", 0)
    avg_avito = avito_data.get("median", avito_data.get("avg", 0))
    count_avito = avito_data.get("count", 0)

    profit = avg_avito - price_wb
    roi = (profit / price_wb * 100) if price_wb > 0 else 0

    if roi > 50 and count_avito < 10:
        verdict = "🔥 ОГОНЬ! Бери не думая!"
    elif roi > 30:
        verdict = "👍 Отличный вариант"
    elif roi > 10:
        verdict = "🤔 Норм, но маржа маловата"
    elif roi > 0:
        verdict = "😐 Почти без прибыли. Думай."
    else:
        verdict = "👎 Мимо. Не трогай."

    if count_avito <= 3:
        demand = "🏆 Дефицит! Мало конкурентов"
    elif count_avito <= 10:
        demand = "📊 Средняя конкуренция"
    else:
        demand = "📉 Много продавцов"

    return (
        f"📦 *{wb_data.get('name', 'Товар')}*\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *WB:* {int(price_wb):,} ₽\n"
        f"💵 *Авито (сред):* {int(avg_avito):,} ₽\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 *Прибыль:* {int(profit):,} ₽ ({roi:+.0f}%)\n"
        f"📊 *Объявлений:* {count_avito} шт.\n"
        f"⚡ *Спрос:* {demand}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*Вердикт:* {verdict}\n\n"
        f"⭐ Рейтинг WB: {wb_data.get('rating', '?')} | Отзывов: {wb_data.get('reviews', '?')}"
    )

# ================== ХЕНДЛЕРЫ ==================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🚀 *ProfitRessel — Оценщик перепродажи*\n\n"
        "Скинь ссылку на товар с Wildberries, и я покажу:\n"
        "• Цену на WB\n"
        "• Среднюю цену на Авито\n"
        "• Потенциальную прибыль\n"
        "• Уровень конкуренции\n\n"
        "_Отправляй ссылку прямо сейчас!_",
        parse_mode="Markdown"
    )

@dp.message()
async def handle_link(message: Message):
    text = message.text.strip() if message.text else ""

    if text.isdigit() and len(text) >= 7:
        text = f"https://www.wildberries.ru/catalog/{text}/detail.aspx"

    if "wildberries.ru" not in text:
        await message.reply("❌ Пришли ссылку на Wildberries!\nПример: https://www.wildberries.ru/catalog/12345678/detail.aspx")
        return

    wait_msg = await message.reply("🔄 *Собираю данные...*", parse_mode="Markdown")

    try:
        wb_result = await parse_wb(text)

        if "error" in wb_result:
            await wait_msg.edit_text(f"❌ {wb_result['error']}")
            return

        avito_result = await parse_avito(wb_result.get("name", ""))
        result_text = format_analysis(wb_result, avito_result)

        await wait_msg.edit_text(result_text, parse_mode="Markdown")
        logger.info(f"Проверили: {wb_result.get('name', '')}")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await wait_msg.edit_text(f"❌ Ошибка: {e}")

# ================== ЗАПУСК ==================
async def main():
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
