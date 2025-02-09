import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

API_TOKEN = '7550289263:AAGbz17PpdoqItrtA1tiWyc_f2mhP_nd220'
ADMIN_ID = 1125145067  # Укажите ID администратора

logging.basicConfig(level=logging.INFO)


bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

conn = sqlite3.connect("events.db")
cursor = conn.cursor()

# Создаем таблицы
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    categories TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    date TEXT,
    location TEXT,
    category TEXT,
    description TEXT
)
""")
conn.commit()

# Фиксированные категории
FIXED_CATEGORIES = ["Музыка", "Спорт", "Кино", "Театр", "Наука", "Технологии"]


def get_user_categories(user_id):
    """Получает список выбранных пользователем категорий"""
    cursor.execute("SELECT categories FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0].split(",") if row and row[0] else []


def set_user_categories(user_id, categories):
    """Сохраняет категории пользователя"""
    categories_str = ",".join(categories)
    cursor.execute(
        "INSERT INTO users (user_id, categories) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET categories = ?",
        (user_id, categories_str, categories_str))
    conn.commit()


def get_categories():
    """Возвращает список всех категорий"""
    return FIXED_CATEGORIES


def generate_category_keyboard(user_id):
    """Создаёт inline-клавиатуру с категориями, где выбранные категории отмечены"""
    user_categories = get_user_categories(user_id)
    buttons = []

    for category in get_categories():
        text = f"✅ {category}" if category in user_categories else category
        buttons.append(InlineKeyboardButton(text=text, callback_data=f"category_{category}"))

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton(text="✅ Завершить выбор", callback_data="finish_selection")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.message(Command("start"))
async def start(message: types.Message):
    """Обрабатывает команду /start и отправляет клавиатуру выбора категорий"""
    user_id = message.from_user.id
    await message.answer("Выберите категории:", reply_markup=generate_category_keyboard(user_id))


@dp.callback_query(lambda c: c.data.startswith("category_"))
async def handle_category_selection(callback: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку категории"""
    category = callback.data.split("_", 1)[1]
    user_id = callback.from_user.id

    user_categories = get_user_categories(user_id)

    if category in user_categories:
        user_categories.remove(category)
    else:
        user_categories.append(category)

    set_user_categories(user_id, user_categories)

    await callback.message.edit_text("Выберите категории:", reply_markup=generate_category_keyboard(user_id))
    await callback.answer()


@dp.callback_query(lambda c: c.data == "finish_selection")
async def finish_selection(callback: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку 'Завершить выбор'"""
    user_id = callback.from_user.id
    selected_categories = get_user_categories(user_id)

    if selected_categories:
        await callback.message.edit_text(f"✅ Вы выбрали категории:\n<b>{', '.join(selected_categories)}</b>",
                                         parse_mode=ParseMode.HTML)

        # Отправляем кнопки "Подборка мероприятий" и "Выбрать заново"
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📌 Подборка мероприятий")],
                [KeyboardButton(text="🔄 Выбрать заново")]
            ],
            resize_keyboard=True
        )
        await callback.message.answer("Что хотите сделать дальше?", reply_markup=keyboard)
    else:
        await callback.message.edit_text("❌ Вы не выбрали ни одной категории.")

    await callback.answer()


@dp.message(lambda message: message.text == "📌 Подборка мероприятий")
async def handle_pick(message: types.Message):
    """Обрабатывает кнопку 'Подборка мероприятий'"""
    await show_events(message)


@dp.message(lambda message: message.text == "🔄 Выбрать заново")
async def handle_choose_new_categories(message: types.Message):
    """Позволяет пользователю выбрать категории заново"""
    await start(message)


@dp.message(Command("events"))
async def show_events(message: types.Message):
    """Показывает список мероприятий в выбранных категориях"""
    user_categories = get_user_categories(message.from_user.id)
    if not user_categories:
        await message.answer("Вы не выбрали ни одной категории. Используйте /start, чтобы выбрать.")
        return

    cursor.execute("SELECT title, date, location FROM events WHERE category IN ({})".format(
        ','.join('?' * len(user_categories))), user_categories)
    events = cursor.fetchall()

    if events:
        events_list = "\n\n".join([f"🎭 <b>{title}</b>\n📅 {date}\n📍 {location}" for title, date, location in events])
        await message.answer(f"📆 <b>Ближайшие мероприятия:</b>\n\n{events_list}", parse_mode=ParseMode.HTML)
    else:
        await message.answer("Нет предстоящих мероприятий в выбранных категориях.")


@dp.message(Command("admin_help"))
async def admin_help(message: types.Message):
    """Выводит список команд администратора"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Вам недоступна данная команда.")
        return

    admin_commands = """
<b>Команды администратора:</b>
/list_events – Показать все мероприятия
/add_event - Добавить мероприятие
/delete_event [номер] – Удалить мероприятие по ID
/notify_users [номер] - Напомнить о мероприятии по ID
"""
    await message.answer(admin_commands, parse_mode=ParseMode.HTML)


@dp.message(Command("list_events"))
async def list_events(message: types.Message):
    """Выводит список всех мероприятий (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    cursor.execute("SELECT id, title, date, category FROM events")
    events = cursor.fetchall()
    if events:
        events_list = "\n".join([f"{event[0]}. {event[1]} - {event[2]} (Категория: {event[3]})" for event in events])
        await message.answer(f"Список мероприятий:\n{events_list}")
    else:
        await message.answer("Нет мероприятий в базе данных.")


@dp.message(Command("delete_event"))
async def delete_event(message: types.Message):
    """Удаляет мероприятие по номеру (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    try:
        event_id = int(message.text.split(' ')[1])
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        await message.answer(f"Мероприятие с номером {event_id} удалено!")
    except:
        await message.answer("Ошибка! Используйте команду: /delete_event <номер мероприятия>")


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


class AddEvent(StatesGroup):
    choosing_category = State()
    entering_title = State()
    entering_date = State()
    entering_description = State()
    entering_location = State()


@dp.message(Command("add_event"))
async def add_event_start(message: types.Message, state: FSMContext):
    """Начинает процесс добавления мероприятия"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=category, callback_data=f"event_category_{category}")]
        for category in FIXED_CATEGORIES
    ])

    await message.answer("Выберите категорию мероприятия:", reply_markup=keyboard)
    await state.set_state(AddEvent.choosing_category)


@dp.callback_query(lambda c: c.data.startswith("event_category_"))
async def choose_category(callback: types.CallbackQuery, state: FSMContext):
    """Сохраняет выбранную категорию"""
    category = callback.data.split("_", 2)[2]
    await state.update_data(category=category)

    await callback.message.answer("Введите название мероприятия:")
    await state.set_state(AddEvent.entering_title)
    await callback.answer()


@dp.message(AddEvent.entering_title)
async def enter_title(message: types.Message, state: FSMContext):
    """Сохраняет название мероприятия"""
    await state.update_data(title=message.text)

    await message.answer("Введите дату и время мероприятия (например, 25.03.2024 18:00):")
    await state.set_state(AddEvent.entering_date)


@dp.message(AddEvent.entering_date)
async def enter_date(message: types.Message, state: FSMContext):
    """Сохраняет дату и время мероприятия"""
    await state.update_data(date=message.text)

    await message.answer("Введите описание мероприятия:")
    await state.set_state(AddEvent.entering_description)


@dp.message(AddEvent.entering_description)
async def enter_description(message: types.Message, state: FSMContext):
    """Сохраняет описание мероприятия"""
    await state.update_data(description=message.text)

    await message.answer("Введите место проведения мероприятия:")
    await state.set_state(AddEvent.entering_location)


@dp.message(AddEvent.entering_location)
async def enter_location(message: types.Message, state: FSMContext):
    """Сохраняет место проведения и завершает добавление"""
    event_data = await state.get_data()
    category = event_data["category"]
    title = event_data["title"]
    date = event_data["date"]
    description = event_data["description"]
    location = message.text

    cursor.execute("INSERT INTO events (title, date, category, description, location) VALUES (?, ?, ?, ?, ?)",
                   (title, date, category, description, location))
    conn.commit()

    await message.answer(
        f"✅ Мероприятие успешно добавлено:\n\n<b>{title}</b>\n📅 {date}\n📍 {location}\n📖 {description}\n📂 Категория: {category}",
        parse_mode=ParseMode.HTML)

    await state.clear()

@dp.message(Command("notify_users"))
async def notify_users(message: types.Message):
    """Оповещает пользователей о мероприятии по ID (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        event_id = int(message.text.split(" ")[1])  # Получаем ID мероприятия
        cursor.execute("SELECT title, date, category, location, description FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()

        if not event:
            await message.answer("❌ Мероприятие с таким ID не найдено.")
            return

        title, date, category, location, description = event

        # Находим пользователей, выбравших данную категорию
        cursor.execute("SELECT user_id FROM users WHERE categories LIKE ?", (f"%{category}%",))
        users = cursor.fetchall()

        if not users:
            await message.answer(f"⚠ Никто не выбрал категорию {category}, уведомления не отправлены.")
            return

        # Формируем текст уведомления
        notification_text = (
            f"📢 <b>Напоминание о мероприятии!</b>\n\n"
            f"🎭 <b>{title}</b>\n"
            f"📅 {date}\n"
            f"📍 {location}\n"
            f"📖 {description}\n\n"
            f"🔥 Не пропустите!"
        )

        # Отправляем уведомление каждому пользователю
        sent_count = 0
        for user in users:
            try:
                await bot.send_message(user[0], notification_text, parse_mode=ParseMode.HTML)
                sent_count += 1
            except Exception as e:
                logging.warning(f"Не удалось отправить сообщение пользователю {user[0]}: {e}")

        await message.answer(f"✅ Уведомления успешно отправлены {sent_count} пользователям.")

    except (IndexError, ValueError):
        await message.answer("❌ Используйте команду так: /notify_users <ID_мероприятия>")



async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
