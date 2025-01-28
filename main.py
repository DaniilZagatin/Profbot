import json
from datetime import datetime, timedelta, time
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Список администраторов
ADMINS = [1125145067]  # Замените числа на реальные chat_id

# Токен вашего бота
TOKEN = "7550289263:AAGbz17PpdoqItrtA1tiWyc_f2mhP_nd220"

# Файлы для хранения данных
EVENTS_FILE = "events.json"
USERS_FILE = "users.json"


# Загрузка данных из JSON
def load_data(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            data = f.read().strip()
            return json.loads(data) if data else []
    except (FileNotFoundError, json.JSONDecodeError):
        save_data(file, [])  # Перезаписываем файл пустым списком
        return []

# Сохранение данных в JSON
def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Добавление нового пользователя
def add_user(chat_id):
    users = load_data(USERS_FILE)
    if chat_id not in users:
        users.append(chat_id)
        save_data(USERS_FILE, users)

# Удаление прошедших мероприятий
def remove_past_events():
    events = load_data(EVENTS_FILE)
    today = datetime.now().date()
    updated_events = [event for event in events if datetime.strptime(event["date"], "%d.%m.%Y").date() >= today]
    if len(updated_events) != len(events):  # Если список изменился, перезаписываем файл
        save_data(EVENTS_FILE, updated_events)

# Уведомление пользователей за день до мероприятия
def notify_users(context: CallbackContext):
    remove_past_events()  # Удаляем прошедшие мероприятия
    events = load_data(EVENTS_FILE)
    users = load_data(USERS_FILE)
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    for event in events:
        event_date = datetime.strptime(event["date"], "%d.%m.%Y").date()
        if event_date == tomorrow:
            message = (
                f"Напоминание о мероприятии:\n\n"
                f"🎉 {event['title']}\n📅 Дата: {event['date']}\n⏰ Время: {event['time']}\n📍 Место: {event['place']}\n"
            )
            for user in users:
                context.bot.send_message(chat_id=user, text=message)

# Команда /start
async def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    add_user(chat_id)
    await update.message.reply_text(
        "Привет! Я бот для информирования о мероприятиях. "
        "Введите /events, чтобы узнать список мероприятий, или ждите уведомлений!"
    )

# Команда /events для отображения списка мероприятий
async def events_list(update: Update, context: CallbackContext):
    remove_past_events()  # Удаляем прошедшие мероприятия перед отображением
    events = load_data(EVENTS_FILE)
    if events:
        text = "Вот список предстоящих мероприятий:\n\n"
        for event in events:
            text += f"🎉 {event['title']}\n📅 Дата: {event['date']}\n⏰ Время: {event['time']}\n📍 Место: {event['place']}\n\n"
    else:
        text = "Сейчас мероприятий нет."
    await update.message.reply_text(text)

# Команда для добавления мероприятий
async def add_event(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        await update.message.reply_text("У вас нет прав для добавления мероприятий.")
        return

    if context.args:
        try:
            # Парсим данные из аргументов
            title, date, time, place = ' '.join(context.args).split(";")
            events = load_data(EVENTS_FILE)
            events.append({"title": title.strip(), "date": date.strip(), "time": time.strip(), "place": place.strip()})
            save_data(EVENTS_FILE, events)
            await update.message.reply_text("Мероприятие добавлено!")
        except ValueError:
            await update.message.reply_text("Ошибка! Используйте формат: название; дата; время; место")
    else:
        await update.message.reply_text("Введите данные в формате: название; дата; время; место")

async def get_id(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Ваш chat_id: {chat_id}")

# Основная функция
def main():
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Удаляем прошедшие мероприятия при запуске бота
    remove_past_events()

    # Настраиваем ежедневное уведомление в 9:00 утра
    job_queue = application.job_queue
    job_queue.run_daily(notify_users, time=time(15, 0))

    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("events", events_list))
    application.add_handler(CommandHandler("add_event", add_event))
    application.add_handler(CommandHandler("get_id", get_id))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
