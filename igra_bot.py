import asyncio
import logging
import json
import os
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8651436301:AAFS7No4WNsaDX9F9ip7KzbY1Mi6j46UnuM"
OWNER_ID = 8260588511  # Твой ID установлен сюда
LOG_FILE = "bot_log.txt"
DB_FILE = "users_db.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ (JSON) ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "usernames": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def init_user(db, user_id, username=None):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "coins": 100,
            "gold": 0,
            "diamonds": 0,
            "last_farm": None
        }
    if username:
        # Привязываем юзернейм к ID для админки
        db["usernames"][username.lower().replace("@", "")] = uid

# --- СОСТОЯНИЯ ДЛЯ АДМИНКИ И ОБМЕНА ---
class AdminGiveState(StatesGroup):
    currency = State()
    amount = State()
    target_user = State()

class ExchangeState(StatesGroup):
    currency = State()
    amount = State()

# Фоновая функция, которую ты просил оставить при запуске
async def check_loans_loop():
    while True:
        # Здесь может быть логика проверки кредитов, пока просто спим
        await asyncio.sleep(3600)

# --- ИГРОВЫЕ КОМАНДЫ (ДЛЯ ЧАТА) ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db = load_db()
    init_user(db, message.from_user.id, message.from_user.username)
    save_db(db)
    await message.reply(
        "🎮 **Привет! Добро пожаловать в игровой бот!**\n\n"
        "📜 **Доступные команды:**\n"
        "🔹 `/profile` (или `профиль`) — Твой баланс и ID\n"
        "🔹 `/farm` (или `сбор`) — Собрать ежечасный бонус коинов\n"
        "🔹 `/exchange` (или `обмен`) — Обменять коины на золото/алмазы\n"
        "🔹 `/casino [валюта] [ставка]` — Игровой автомат\n"
        "🔹 `/darts [валюта] [ставка]` — Игра в Дартс\n"
        "🔹 `/football [валюта] [ставка]` — Футбол\n"
        "🔹 `/basketball [валюта] [ставка]` — Баскетбол\n\n"
        "Доступные валюты для игр: `коины`, `золото`, `алмазы`"
    )

@dp.message(F.text.lower().in_({"профиль", "/profile"}))
async def cmd_profile(message: types.Message):
    db = load_db()
    init_user(db, message.from_user.id, message.from_user.username)
    u = db["users"][str(message.from_user.id)]
    
    text = (
        f"👤 **Профиль игрока:**\n"
        f"📝 Юзернейм: @{message.from_user.username or 'отсутствует'}\n"
        f"🆔 ID: `{message.from_user.id}`\n"
        f"---------------------------\n"
        f"💰 Коины: {u['coins']}\n"
        f"👑 Золото: {u['gold']}\n"
        f"💎 Алмазы: {u['diamonds']}"
    )
    await message.reply(text, parse_mode="Markdown")

@dp.message(F.text.lower().in_({"сбор", "farm", "/farm"}))
async def cmd_farm(message: types.Message):
    db = load_db()
    uid = str(message.from_user.id)
    init_user(db, message.from_user.id, message.from_user.username)
    
    user_data = db["users"][uid]
    now = datetime.now()
    
    if user_data["last_farm"]:
        last_farm_time = datetime.fromisoformat(user_data["last_farm"])
        if now - last_farm_time < timedelta(hours=1):
            remaining = timedelta(hours=1) - (now - last_farm_time)
            minutes = int(remaining.seconds // 60)
            await message.reply(f"⏳ Вы уже собирали ресурсы! Подождите ещё {minutes} мин.")
            return

    # За 24 часа выходит ~200 коинов, значит за 1 час даём примерно 8 коинов
    reward = 8
    user_data["coins"] += reward
    user_data["last_farm"] = now.isoformat()
    save_db(db)
    
    await message.reply(f"🚜 Вы успешно провели сбор! Получено: `+{reward} коинов`💰")

# --- СИСТЕМА ОБМЕНА ВАЛЮТ ---

@dp.message(Command("exchange"))
@dp.message(F.text.lower() == "обмен")
async def cmd_exchange(message: types.Message, state: FSMContext):
    await state.set_state(ExchangeState.currency)
    await message.reply(
        "💱 **Обмен валют**\n"
        "Курс обмена:\n"
        "🔸 20 Коинов = 1 Алмаз\n"
        "🔸 30 Коинов = 1 Золото\n\n"
        "Выберите валюту, которую хотите **получить** (напишите `алмазы` или `золото`):"
    )

@dp.message(ExchangeState.currency)
async def exchange_currency(message: types.Message, state: FSMContext):
    choice = message.text.lower().strip()
    if choice not in ["алмазы", "золото"]:
        await message.reply("❌ Неверный выбор. Введите `алмазы` или `золото`:")
        return
    await state.update_data(target=choice)
    await state.set_state(ExchangeState.amount)
    await message.reply(f"Введите количество **{choice}**, которое хотите получить:")

@dp.message(ExchangeState.amount)
async def exchange_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Введите корректное число больше нуля:")
        return

    data = await state.get_data()
    target = data["target"]
    rate = 20 if target == "алмазы" else 30
    required_coins = amount * rate

    db = load_db()
    uid = str(message.from_user.id)
    init_user(db, message.from_user.id, message.from_user.username)
    
    if db["users"][uid]["coins"] < required_coins:
        await message.reply(f"❌ Недостаточно коинов! Для получения {amount} {target} нужно {required_coins} коинов. Используйте `/farm` для заработка.")
        await state.clear()
        return

    # Сохраняем данные для подтверждения
    await state.update_data(amount=amount, cost=required_coins)
    
    # Создаем кнопку подтверждения прямо в тексте (или клавиатурой)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Подтвердить обмен", callback_data="confirm_ex")]
    ])
    await message.reply(f"📊 Вы хотите получить {amount} {target} за {required_coins} коинов. Подтвердите операцию:", reply_markup=kb)

@dp.callback_query(F.data == "confirm_ex")
async def confirm_exchange(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await callback.answer("Сессия истекла.", show_alert=True)
        return

    target = data["target"]
    amount = data["amount"]
    cost = data["cost"]
    
    db = load_db()
    uid = str(callback.from_user.id)
    
    if db["users"][uid]["coins"] < cost:
        await callback.answer("Ошибка: недостаточно коинов!", show_alert=True)
        await state.clear()
        return

    db["users"][uid]["coins"] -= cost
    if target == "алмазы":
        db["users"][uid]["diamonds"] += amount
    else:
        db["users"][uid]["gold"] += amount
        
    save_db(db)
    await callback.message.edit_text(f"💳 У вас списалось {cost} коинов. Вы получили {amount} {target}! 🎉")
    await state.clear()

# --- ИГРОВОЙ БЛОК ---

def parse_bet(message_text, user_data):
    # Парсинг команды вида /game коины 500
    parts = message_text.split()
    if len(parts) < 3:
        return None, None, "❌ Правильное использование команды: `/[игра] [валюта] [ставка]`\nПример: `/casino коины 100`"
    
    currency_input = parts[1].lower()
    if currency_input in ["коины", "коин", "coins"]:
        curr = "coins"
    elif currency_input in ["золото", "gold"]:
        curr = "gold"
    elif currency_input in ["алмазы", "алмаз", "diamonds"]:
        curr = "diamonds"
    else:
        return None, None, "❌ Неверная валюта! Используйте: `коины`, `золото` или `алмазы`."

    try:
        bet = int(parts[2])
        if bet <= 0:
            raise ValueError
    except ValueError:
        return None, None, "❌ Ставка должна быть целым числом больше 0!"

    if user_data[curr] < bet:
        return None, None, f"❌ У вас недостаточно ресурсов этой валюты! Баланс позволяет играть, только если хватает средств. Попробуйте `/farm`."

    return curr, bet, None

@dp.message(Command("casino"))
async def game_casino(message: types.Message):
    db = load_db()
    uid = str(message.from_user.id)
    init_user(db, message.from_user.id, message.from_user.username)
    
    curr, bet, error = parse_bet(message.text, db["users"][uid])
    if error:
        await message.reply(error)
        return

    # Слот-машина на эмодзи
    slots = ["🍇", "7️⃣", "🍫", "🍋"]
    res = [random.choice(slots) for _ in range(3)]
    res_str = " | ".join(res)
    
    db["users"][uid][curr] -= bet

    # Проверка условий выигрыша
    if res[0] == res[1] == res[2]:
        # Три одинаковых символа (Джекпот)
        win = bet * 3
        db["users"][uid][curr] += win
        out = f"🎰 **КАЗИНO** 🎰\n\nРезультат: [ {res_str} ]\n\n🔥 **ВЫИГРЫШ!** Три в ряд! Вы забрали {win} {message.text.split()[1]}!"
    elif res[0] == res[1] or res[1] == res[2] or res[0] == res[2]:
        # Два одинаковых символа
        win = int(bet * 1.5)
        db["users"][uid][curr] += win
        out = f"🎰 **КАЗИНO** 🎰\n\nРезультат: [ {res_str} ]\n\n🎉 **ВЫИГРЫШ!** Два одинаковых символа! Приз умножен: +{win} {message.text.split()[1]}!"
    else:
        out = f"🎰 **КАЗИНO** 🎰\n\nРезультат: [ {res_str} ]\n\n🛑 **Вы проиграли!** В следующий раз повезёт."

    save_db(db)
    await message.reply(out)

@dp.message(Command("darts"))
async def game_darts(message: types.Message):
    db = load_db()
    uid = str(message.from_user.id)
    init_user(db, message.from_user.id, message.from_user.username)
    
    curr, bet, error = parse_bet(message.text, db["users"][uid])
    if error:
        await message.reply(error)
        return

    db["users"][uid][curr] -= bet
    # Шанс попасть ровно в цель (яблочко) - 30%
    if random.random() < 0.30:
        win = bet * 3
        db["users"][uid][curr] += win
        out = f"🎯 **ДАРТС** 🎯\n\n🎯 Вы попали **ровно в яблочко центpа мишени**!\n\n💰 Ваш приз умножен: +{win} {message.text.split()[1]}!"
    else:
        out = f"🎯 **ДАРТС** 🎯\n\n❌ Вы не попали в цель и промахнулись. Вы проиграли, попробуйте еще раз, вдруг вам повезёт!"

    save_db(db)
    await message.reply(out)

@dp.message(Command("football"))
async def game_football(message: types.Message):
    db = load_db()
    uid = str(message.from_user.id)
    init_user(db, message.from_user.id, message.from_user.username)
    
    curr, bet, error = parse_bet(message.text, db["users"][uid])
    if error:
        await message.reply(error)
        return

    db["users"][uid][curr] -= bet
    outcome = random.choice(["left", "center", "right", "far_away", "almost"])

    if outcome in ["left", "center", "right"]:
        win = bet * 2
        db["users"][uid][curr] += win
        out = f"⚽ **ФУТБОЛ** ⚽\n\n⚡ ГОЛ! Мяч залетел ровно в сетку ворот! Награда: +{win} {message.text.split()[1]}!"
    elif outcome == "far_away":
        out = f"⚽ **ФУТБОЛ** ⚽\n\n❌ Удар мимо ворот, мяч улетел слишком далеко... Вы проиграли к сожалению."
    else:
        out = f"⚽ **ФУТБОЛ** ⚽\n\n❌ Мяч почти долетел до сетки, но вратарь поймал его! Это проигрышь."

    save_db(db)
    await message.reply(out)

@dp.message(Command("basketball"))
async def game_basketball(message: types.Message):
    db = load_db()
    uid = str(message.from_user.id)
    init_user(db, message.from_user.id, message.from_user.username)
    
    curr, bet, error = parse_bet(message.text, db["users"][uid])
    if error:
        await message.reply(error)
        return

    db["users"][uid][curr] -= bet
    # Шанс попадания в кольцо - 45%
    if random.random() < 0.45:
        win = bet * 2
        db["users"][uid][curr] += win
        out = f"🏀 **БАСКЕТБОЛ** 🏀\n\n🏀 Точный бросок! Мяч залетает ровно в сетку кольца!\n💰 Сумма умножается: Вы выиграли +{win} {message.text.split()[1]}!"
    else:
        out = f"🏀 **БАСКЕТБОЛ** 🏀\n\n❌ Промах! Мяч ударился о дужку кольца. Вы проиграли."

    save_db(db)
    await message.reply(out)

# --- АДМИН-ПАНЕЛЬ ВЛАДЕЛЬЦА (ВЫДАЧА РЕСУРСОВ) ---

@dp.message(Command("give"))
async def admin_give_start(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return # Игнорируем не-владельцев

    await state.set_state(AdminGiveState.currency)
    await message.reply("👑 **Админ-панель**\nВыберите валюту для выдачи (`алмазы`, `золото`, `коины`):")

@dp.message(AdminGiveState.currency)
async def admin_choose_curr(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    choice = message.text.lower().strip()
    
    if choice in ["алмазы", "алмаз"]: curr = "diamonds"
    elif choice in ["золото", "золот"]: curr = "gold"
    elif choice in ["коины", "коин"]: curr = "coins"
    else:
        await message.reply("❌ Выберите корректную валюту (`алмазы`, `золото`, `коины`):")
        return

    await state.update_data(currency=curr, currency_name=choice)
    await state.set_state(AdminGiveState.amount)
    await message.reply(f"Введите сумму {choice} (от 1 до бесконечности):")

@dp.message(AdminGiveState.amount)
async def admin_enter_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    try:
        amount = int(message.text)
        if amount <= 0: raise ValueError
    except ValueError:
        await message.reply("❌ Введите валидное число больше нуля:")
        return

    await state.update_data(amount=amount)
    await state.set_state(AdminGiveState.target_user)
    await message.reply("Введите юзернейм (например, `@dd_nickname`) или Telegram ID игрока:")

@dp.message(AdminGiveState.target_user)
async def admin_process_give(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    target_input = message.text.strip()
    
    data = await state.get_data()
    curr = data["currency"]
    curr_name = data["currency_name"]
    amount = data["amount"]
    
    db = load_db()
    target_id = None

    # Пытаемся понять, передан ID или юзернейм
    if target_input.isdigit():
        target_id = target_input
    else:
        clean_username = target_input.replace("@", "").lower()
        target_id = db["usernames"].get(clean_username)

    if not target_id:
        await message.reply("❌ Пользователь не найден в базе данных бота. Ему нужно хотя бы раз написать боту `/start`.")
        await state.clear()
        return

    # Инициализируем и выдаем ресурсы
    init_user(db, target_id)
    db["users"][str(target_id)][curr] += amount
    save_db(db)

    # Уведомляем админа
    await message.reply(f"✅ Я выдал этому данному человеку {amount} {curr_name}.")

    # Уведомляем игрока
    try:
        await bot.send_message(
            chat_id=int(target_id),
            text=f"🎁 Вам администратор выдал {amount} {curr_name}!"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {target_id}: {e}")

    await state.clear()

# --- ТОЧКА ВХОДА И ИСПРАВЛЕННЫЙ ЗАПУСК ---

async def main():
    # Твой исправленный блок инициализации при старте
    logger.info(f"👑 Владелец: {OWNER_ID}")
    
    # Запуск фоновой автоматической проверки кредитов (заглушка работает)
    asyncio.create_task(check_loans_loop())
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n--- Бот запущен {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        
    print("🚀 Бот успешно запущен и готов к играм!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
