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

# ================== ПАРСЕР ОДНОГО ОБЪЯВЛЕНИЯ ==================
async def parse_avito_ad(url: str) -> dict:
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
            if not title_tag:
                title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else "Без названия"
            # Убираем "купить", "в Москве" и прочий мусор из title
            title = re.sub(r'купить\s+|в\s+\S+\s*|цена\s*|недорого\s*|бу\s*|нов(ая|ый|ое)\s*', '', title, flags=re.IGNORECASE).strip()

            # Цена (meta itemprop)
            price_tag = soup.find("meta", itemprop="price")
            price = 0
            if price_tag:
                content = price_tag.get("content")
                if content:
                    price = float(content)

            # Fallback: span с ценой
            if price == 0:
                price_span = soup.find("span", {"data-marker": "item-view/item-price"})
                if price_span:
                    text = price_span.get_text(strip=True)
                    nums = re.findall(r'[\d\s]+', text)
                    if nums:
                        num = nums[0].replace(" ", "").replace("\xa0", "")
                        try:
                            price = float(num)
                        except:
                            pass

            # Город — много вариантов
            city = "Не указан"
            city_selectors = [
                ("span", {"data-marker": "item-view/item-address"}),
                ("span", {"class": re.compile(r"address")}),
                ("a", {"data-marker": "item-view/breadcrumbs"}),
                ("meta", {"itemprop": "addressLocality"}),
            ]
            for tag_name, attrs in city_selectors:
                city_tag = soup.find(tag_name, attrs)
                if city_tag:
                    if tag_name == "meta":
                        city = city_tag.get("content", "Не указан")
                    else:
                        city = city_tag.get_text(strip=True)
                    break

            # Категория
            breadcrumbs = soup.find_all("a", {"data-marker": "item-view/breadcrumbs"})
            category = " > ".join([b.get_text(strip=True) for b in breadcrumbs]) if breadcrumbs else "Не указана"

            # Просмотры
            views = 0
            views_selectors = [
                ("span", {"data-marker": "item-view/total-views"}),
                ("span", string=re.compile(r"просмотр|view", re.IGNORECASE)),
                ("span", {"class": re.compile(r"views")}),
            ]
            for tag_name, attrs in views_selectors:
                views_tag = soup.find(tag_name, attrs)
                if views_tag:
                    views_text = views_tag.get_text(strip=True) if tag_name != "meta" else views_tag.get("content", "")
                    views_match = re.search(r'(\d[\d\s]*)', views_text)
                    if views_match:
                        views = int(views_match.group(1).replace(" ", ""))
                        break

            # Дата
            date_tag = soup.find("span", {"data-marker": "item-view/item-date"})
            if not date_tag:
                date_tag = soup.find("span", string=re.compile(r'сегодня|вчера|день|час|мин|\d{1,2}\s+\w+', re.IGNORECASE))
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

# ================== ПОИСК ПОХОЖИХ ==================
async def search_similar_avito(title: str) -> dict:
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.8",
    }

    # Берём 3-5 ключевых слов без спецсимволов
    clean_title = re.sub(r'[^\w\s]', '', title)
    words = clean_title.split()
    # Убираем короткие слова и мусор
    keywords = [w for w in words if len(w) > 2 and w.lower() not in ['sim', 'esim', 'гб', 'гб,', 'pro', 'max', 'для', 'для', 'для']]
    if not keywords:
        keywords = words[:3]
    short_query = " ".join(keywords[:4])
    
    search_url = f"https://www.avito.ru/all?q={short_query}"
    logger.info(f"Ищем на Авито: {short_query}")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            resp = await client.get(search_url, headers=headers, timeout=15)

            if resp.status_code != 200:
                return {"error": f"Авито ответил {resp.status_code}", "prices": [], "avg": 0, "median": 0, "count": 0}

            soup = BeautifulSoup(resp.text, "html.parser")
            
            prices = []
            
            # Способ 1: meta itemprop="price"
            price_items = soup.find_all("meta", itemprop="price")
            for item in price_items:
                content = item.get("content")
                if content:
                    try:
                        p = float(content)
                        if p > 0:
                            prices.append(p)
                    except:
                        continue

            # Способ 2: span с data-marker="item-price"
            if not prices:
                price_blocks = soup.find_all("span", {"data-marker": re.compile(r"item-price")})
                for block in price_blocks:
                    text = block.get_text(strip=True)
                    nums = re.findall(r'[\d\s]+', text)
                    if nums:
                        num = nums[0].replace(" ", "").replace("\xa0", "")
                        try:
                            p = float(num)
                            if 100 < p < 50_000_000:
                                prices.append(p)
                        except:
                            continue

            # Способ 3: любые span с ценой
            if not prices:
                price_blocks = soup.find_all("span", class_=re.compile(r".*price.*"))
                for block in price_blocks:
                    text = block.get_text(strip=True)
                    nums = re.findall(r'[\d\s]+', text)
                    if nums:
                        num = nums[0].replace(" ", "").replace("\xa0", "")
                        try:
                            p = float(num)
                            if 100 < p < 50_000_000:
                                prices.append(p)
                        except:
                            continue

            if not prices:
                return {"error": "Не удалось найти похожие товары на Авито", "prices": [], "avg": 0, "median": 0, "count": 0}

            # Фильтруем выбросы
            sorted_prices = sorted(prices)
            median = sorted_prices[len(sorted_prices) // 2]
            filtered = [p for p in prices if 0.3 * median < p < 3 * median]
            
            if filtered:
                sorted_filtered = sorted(filtered)
                avg = sum(filtered) / len(filtered)
                median = sorted_filtered[len(sorted_filtered) // 2]
            else:
                avg = sum(prices) / len(prices)

            return {
                "prices": sorted(prices)[:10],
                "avg": round(avg, 2),
                "median": round(median, 2),
                "count": len(prices)
            }
        except Exception as e:
            return {"error": f"Ошибка поиска: {str(e)}", "prices": [], "avg": 0, "median": 0, "count": 0}

# ================== АНАЛИЗ ==================
def analyze_profit(ad_data: dict, market_data: dict) -> str:
    if "error" in ad_data:
        return f"❌ Ошибка объявления: {ad_data['error']}"

    if "error" in market_data:
        return (
            f"📦 *{ad_data.get('title', 'Товар')}*\n"
            f"💰 Цена в объявлении: *{int(ad_data.get('price', 0)):,} ₽*\n"
            f"📍 {ad_data.get('city', 'Не указан')} | 👁 {ad_data.get('views', 0)} просмотров\n"
            f"🗓 {ad_data.get('date', 'Не указана')}\n\n"
            f"⚠️ Не удалось найти похожие: {market_data.get('error', '')}"
        )

    price_ad = ad_data.get("price", 0)
    avg_market = market_data.get("median", market_data.get("avg", 0))
    count = market_data.get("count", 0)

    if price_ad == 0 or avg_market == 0:
        return f"📦 *{ad_data.get('title', 'Товар')}*\n💰 Цена: {int(price_ad):,} ₽\n\n⚠️ Недостаточно данных для анализа"

    profit = avg_market - price_ad
    roi = (profit / price_ad * 100) if price_ad > 0 else 0
    discount = ((avg_market - price_ad) / avg_market * 100) if avg_market > 0 else 0

    if roi > 50 and count < 15:
        verdict = "🔥 ОГОНЬ! Срочно бери и перепродавай!"
        emoji = "🟢"
    elif roi > 30:
        verdict = "👍 Отличный вариант для перепродажи"
        emoji = "🟢"
    elif roi > 15:
        verdict = "🤔 Норм, можно взять"
        emoji = "🟡"
    elif roi > 0:
        verdict = "😐 Почти без прибыли"
        emoji = "🟠"
    else:
        verdict = "👎 Дороже рынка. Невыгодно"
        emoji = "🔴"

    if count <= 5:
        competition = "🏆 Низкая (дефицит!)"
    elif count <= 20:
        competition = "📊 Средняя"
    else:
        competition = "📉 Высокая"

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
        "Отправь мне ссылку на объявление Авито — я проанализирую:\n"
        "• Реальную рыночную цену\n"
        "• Потенциальную прибыль\n"
        "• Уровень конкуренции\n\n"
        "_Отправляй ссылку!_",
        parse_mode="Markdown"
    )

@dp.message()
async def handle_message(message: Message):
    text = message.text.strip() if message.text else ""

    if "avito.ru" not in text:
        await message.reply("❌ Пришли ссылку на объявление Авито!")
        return

    wait_msg = await message.reply("🔍 *Анализирую...*", parse_mode="Markdown")

    try:
        ad_data = await parse_avito_ad(text)

        if "error" in ad_data:
            await wait_msg.edit_text(f"❌ {ad_data['error']}")
            return

        market_data = await search_similar_avito(ad_data.get("title", ""))
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
