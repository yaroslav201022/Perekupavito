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

# ================== ПАРСЕР АВИТО (ОДНО ОБЪЯВЛЕНИЕ) ==================
async def parse_avito_ad(url: str) -> dict:
    """Парсит одно объявление Авито по ссылке"""
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.8",
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers, timeout=15)

            if resp.status_code != 200:
                return {"error": f"Авито вернул статус {resp.status_code}"}

            soup = BeautifulSoup(resp.text, "html.parser")

            # Название
            title_tag = soup.find("h1", {"data-marker": "item-view/title-info"})
            if not title_tag:
                title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else "Без названия"

            # Цена
            price_tag = soup.find("meta", itemprop="price")
            price = 0
            if price_tag:
                content = price_tag.get("content")
                if content:
                    price = float(content)

            # Fallback: ищем цену в спанах
            if price == 0:
                price_span = soup.find("span", {"data-marker": "item-view/item-price"})
                if price_span:
                    text = price_span.get_text(strip=True)
                    nums = re.findall(r'[\d\s]+', text)
                    if nums:
                        num = nums[0].replace(" ", "").replace("\xa0", "")
                        price = float(num)

            # Город
            city_tag = soup.find("span", {"data-marker": "item-view/item-address"})
            city = city_tag.get_text(strip=True) if city_tag else "Не указан"

            # Категория (хлебные крошки)
            breadcrumbs = soup.find_all("a", {"data-marker": "item-view/breadcrumbs"})
            category = " > ".join([b.get_text(strip=True) for b in breadcrumbs]) if breadcrumbs else "Не указана"

            # Количество просмотров
            views = 0
            views_tag = soup.find("span", {"data-marker": "item-view/total-views"})
            if views_tag:
                views_text = views_tag.get_text(strip=True)
                views_match = re.search(r'(\d+)', views_text)
                if views_match:
                    views = int(views_match.group(1))

            # Дата публикации
            date_tag = soup.find("span", {"data-marker": "item-view/item-date"})
            date_published = date_tag.get_text(strip=True) if date_tag else "Не указана"

            return {
                "title": title,
                "price": price,
                "city": city,
                "category": category,
                "views": views,
                "date": date_published
            }

        except Exception as e:
            return {"error": f"Ошибка парсинга: {str(e)}"}

# ================== ПОИСК ПОХОЖИХ НА АВИТО ==================
async def search_similar_avito(title: str) -> dict:
    """Ищет похожие товары на Авито и собирает цены"""
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.8",
    }

    short_query = " ".join(title.split()[:5])
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
                        p = float(content)
                        if p > 0:
                            prices.append(p)
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
                            p = float(num)
                            if 100 < p < 10_000_000:
                                prices.append(p)
                        except:
                            continue

            if not prices:
                return {"error": "Не удалось найти похожие товары", "prices": [], "avg": 0, "median": 0, "count": 0}

            avg = sum(prices) / len(prices)
            sorted_prices = sorted(prices)
            median = sorted_prices[len(sorted_prices) // 2]

            # Убираем выбросы: цены, сильно отличающиеся от медианы
            filtered = [p for p in prices if 0.3 * median < p < 3 * median]
            if filtered:
                sorted_filtered = sorted(filtered)
                avg = sum(filtered) / len(filtered)
                median = sorted_filtered[len(sorted_filtered) // 2]

            return {
                "prices": sorted(prices)[:10],
                "avg": round(avg, 2),
                "median": round(median, 2),
                "count": len(prices)
            }
        except Exception as e:
            return {"error": f"Ошибка поиска: {str(e)}", "prices": [], "avg": 0, "median": 0, "count": 0}

# ================== АНАЛИЗ ВЫГОДНОСТИ ==================
def analyze_profit(ad_data: dict, market_data: dict) -> str:
    """Анализирует выгодность перепродажи"""
    if "error" in ad_data:
        return f"❌ Ошибка объявления: {ad_data['error']}"

    if "error" in market_data:
        return (
            f"📦 *{ad_data.get('title', 'Товар')}*\n"
            f"💰 Цена в объявлении: *{int(ad_data.get('price', 0)):,} ₽*\n"
            f"📍 {ad_data.get('city', '?')} | 👁 {ad_data.get('views', '?')} просмотров\n\n"
            f"⚠️ Не удалось найти похожие: {market_data.get('error', '')}"
        )

    price_ad = ad_data.get("price", 0)
    avg_market = market_data.get("median", market_data.get("avg", 0))
    count = market_data.get("count", 0)

    profit = avg_market - price_ad
    roi = (profit / price_ad * 100) if price_ad > 0 else 0
    discount = ((avg_market - price_ad) / avg_market * 100) if avg_market > 0 else 0

    # Вердикт
    if roi > 50 and count < 15:
        verdict = "🔥 ОГОНЬ! Срочно бери и перепродавай!"
        emoji = "🟢"
    elif roi > 30:
        verdict = "👍 Отличный вариант для перепродажи"
        emoji = "🟢"
    elif roi > 15:
        verdict = "🤔 Норм, можно взять, но маржа небольшая"
        emoji = "🟡"
    elif roi > 0:
        verdict = "😐 Почти без прибыли. Поищи дешевле"
        emoji = "🟠"
    else:
        verdict = "👎 Дороже рынка. Невыгодно"
        emoji = "🔴"

    # Конкуренция
    if count <= 5:
        competition = "🏆 Низкая (дефицит!)"
    elif count <= 20:
        competition = "📊 Средняя"
    else:
        competition = "📉 Высокая (много продавцов)"

    return (
        f"{emoji} *Анализ объявления*\n\n"
        f"📦 *{ad_data.get('title', 'Товар')}*\n"
        f"📍 {ad_data.get('city', '?')} | 🗓 {ad_data.get('date', '?')}\n"
        f"👁 Просмотров: {ad_data.get('views', 0)}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *Цена в объявлении:* {int(price_ad):,} ₽\n"
        f"💵 *Средняя рыночная:* {int(avg_market):,} ₽\n"
        f"📉 *Скидка от рынка:* {discount:.0f}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 *Потенциальная прибыль:* {int(profit):,} ₽ ({roi:+.0f}%)\n"
        f"📊 *Конкуренция:* {competition} ({count} объявл.)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*Вердикт:* {verdict}"
    )

# ================== ХЕНДЛЕРЫ ==================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🚀 *ProfitRessel — Оценщик выгоды на Авито*\n\n"
        "📎 *Как пользоваться:*\n"
        "Отправь мне ссылку на любое объявление Авито, и я проанализирую:\n"
        "• Реальную рыночную цену\n"
        "• Потенциальную прибыль при перепродаже\n"
        "• Уровень конкуренции\n"
        "• Выгодно ли брать\n\n"
        "📝 *Пример:*\n"
        "`https://www.avito.ru/moskva/tovary_dlya_kompyutera/igrovaya_mysh_123456789`\n\n"
        "_Отправляй ссылку!_",
        parse_mode="Markdown"
    )

@dp.message()
async def handle_message(message: Message):
    text = message.text.strip() if message.text else ""

    # Проверяем, что это ссылка на Авито
    if "avito.ru" not in text:
        await message.reply(
            "❌ Пришли ссылку на объявление Авито!\n\n"
            "📝 Пример:\n"
            "`https://www.avito.ru/moskva/...`",
            parse_mode="Markdown"
        )
        return

    wait_msg = await message.reply("🔍 *Анализирую объявление...*", parse_mode="Markdown")

    try:
        # 1. Парсим объявление
        ad_data = await parse_avito_ad(text)

        if "error" in ad_data:
            await wait_msg.edit_text(f"❌ {ad_data['error']}")
            return

        # 2. Ищем похожие на рынке
        market_data = await search_similar_avito(ad_data.get("title", ""))

        # 3. Анализируем
        result = analyze_profit(ad_data, market_data)

        await wait_msg.edit_text(result, parse_mode="Markdown")
        logger.info(f"Проанализировали: {ad_data.get('title', '')}")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await wait_msg.edit_text(f"❌ Ошибка: {e}")

# ================== ЗАПУСК ==================
async def main():
    logger.info("Бот ProfitRessel запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
