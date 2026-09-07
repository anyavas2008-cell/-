
# Импортируем библиотеку для работы с Telegram Bot API

import telebot
# Импортируем модуль для создания inline-кнопок
from telebot import types
# Импортируем библиотеку для подключения к PostgreSQL
import psycopg2

# Вставь сюда токен своего бота, полученный от @BotFather
BOT_TOKEN = "8999666334:AAHqq8YdxMn1095k6QAHWuGFKWR55HTU0lk"

# Создаём экземпляр бота
bot = telebot.TeleBot(BOT_TOKEN)

# Глобальный словарь для хранения промежуточных данных пользователя
user_data = {}


# ==========================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
# ==========================================================

def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="urfu_poputka",
        user="postgres",
        password="ТВОЙ_ПАРОЛЬ"
    )
    return conn


# ==========================================================
# ОТМЕНА ДЕЙСТВИЯ — общая функция для любого шага
# ==========================================================

def cancel_action(chat_id):
    # Удаляем накопленные временные данные пользователя (если они были)
    if chat_id in user_data:
        del user_data[chat_id]

    # bot.clear_step_handler_by_chat_id "отменяет" ожидание следующего текстового
    # сообщения, зарегистрированное через register_next_step_handler.
    # Без этой строки бот всё равно попытается обработать следующее сообщение
    # пользователя как ответ на вопрос, который мы отменили.
    bot.clear_step_handler_by_chat_id(chat_id)

    # Достаём имя пользователя из БД, чтобы красиво показать главное меню
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    name = result[0] if result is not None else "друг"

    bot.send_message(chat_id, "❌ Действие отменено.")
    show_main_menu(chat_id, name)


# ==========================================================
# СТАРТ И РЕГИСТРАЦИЯ
# ==========================================================

@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if result is not None:
        name = result[0]
        show_main_menu(chat_id, name)
    else:
        # На регистрации кнопку "Отмена" не ставим — без роли дальше идти некуда
        keyboard = types.InlineKeyboardMarkup()
        driver_button = types.InlineKeyboardButton(text="🚘 Я водитель", callback_data="role_driver")
        passenger_button = types.InlineKeyboardButton(text="🚶 Я пассажир", callback_data="role_passenger")
        keyboard.add(driver_button, passenger_button)
        bot.send_message(
            chat_id,
            "🚗 Добро пожаловать в УрФУ-Попутку!\nВыберите свою роль:",
            reply_markup=keyboard
        )


def show_main_menu(chat_id, name):
    keyboard = types.InlineKeyboardMarkup()
    create_ride_button = types.InlineKeyboardButton(text="🚘 Создать поездку", callback_data="menu_create_ride")
    find_ride_button = types.InlineKeyboardButton(text="🚶 Найти поездку", callback_data="menu_find_ride")
    keyboard.add(create_ride_button, find_ride_button)
    bot.send_message(chat_id, f"👋 Привет, {name}!\nЧто хотите сделать?", reply_markup=keyboard)


def save_name_handler(message, role):
    chat_id = message.chat.id
    name = message.text

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (tg_id, name, role)
        VALUES (%s, %s, %s)
        ON CONFLICT (tg_id) DO UPDATE 
        SET name = EXCLUDED.name, role = EXCLUDED.role
    """, (chat_id, name, role))
    conn.commit()
    cur.close()
    conn.close()

    bot.send_message(chat_id, f"👋 Приятно познакомиться, {name}! Регистрация завершена.")
    show_main_menu(chat_id, name)


# ==========================================================
# СЦЕНАРИЙ ВОДИТЕЛЯ (создание поездки)
# ==========================================================

def start_create_ride(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    to_uni_button = types.InlineKeyboardButton(text="🏫 В ВУЗ", callback_data="dir_to_uni")
    from_uni_button = types.InlineKeyboardButton(text="🏠 ИЗ ВУЗА", callback_data="dir_from_uni")
    cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    # Кнопки направления в один ряд, отмена — отдельным рядом ниже
    keyboard.add(to_uni_button, from_uni_button)
    keyboard.add(cancel_button)
    bot.send_message(chat_id, "🧭 Направление поездки:", reply_markup=keyboard)


def get_district_step(message, chat_id):
    district = message.text
    user_data[chat_id]["district"] = district

    # Для текстовых вопросов прикрепляем клавиатуру только с кнопкой "Отмена" —
    # пользователь либо печатает ответ, либо жмёт отмену
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    msg = bot.send_message(chat_id, "⏰ Во сколько выезжаете? (например: 08:30)", reply_markup=keyboard)
    bot.register_next_step_handler(msg, get_time_step, chat_id)


def get_time_step(message, chat_id):
    time_str = message.text
    user_data[chat_id]["time"] = time_str

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    msg = bot.send_message(chat_id, "🪑 Сколько свободных мест?", reply_markup=keyboard)
    bot.register_next_step_handler(msg, get_seats_step, chat_id)


def get_seats_step(message, chat_id):
    try:
        seats = int(message.text)
    except ValueError:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "⚠️ Введите число, например: 3", reply_markup=keyboard)
        bot.register_next_step_handler(msg, get_seats_step, chat_id)
        return

    user_data[chat_id]["seats"] = seats
    ride = user_data[chat_id]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO rides (driver_tg_id, direction, campus, district, time, seats)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (chat_id, ride["direction"], ride["campus"], ride["district"], ride["time"], ride["seats"]))
    conn.commit()
    cur.close()
    conn.close()

    del user_data[chat_id]

    direction_text = "В ВУЗ" if ride["direction"] == "to_uni" else "ИЗ ВУЗА"
    campus_text = "Новокольцовский" if ride["campus"] == "novokolcovskiy" else "Старый (Мира)"

    bot.send_message(
        chat_id,
        f"✅ Поездка создана!\n"
        f"🧭 {direction_text}  📍 {ride['district']} → {campus_text}\n"
        f"⏰ {ride['time']}  🪑 {ride['seats']} мест"
    )


# ==========================================================
# СЦЕНАРИЙ ПАССАЖИРА (поиск и бронирование поездки)
# ==========================================================

def start_find_ride(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    to_uni_button = types.InlineKeyboardButton(text="🏫 В ВУЗ", callback_data="find_dir_to_uni")
    from_uni_button = types.InlineKeyboardButton(text="🏠 ИЗ ВУЗА", callback_data="find_dir_from_uni")
    cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    keyboard.add(to_uni_button, from_uni_button)
    keyboard.add(cancel_button)
    bot.send_message(chat_id, "🧭 Куда вам нужно?", reply_markup=keyboard)


def find_rides_step(message, chat_id):
    district = message.text
    user_data[chat_id]["district"] = district
    filters = user_data[chat_id]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rides.id, users.name, rides.time, rides.seats, rides.driver_tg_id
        FROM rides
        JOIN users ON rides.driver_tg_id = users.tg_id
        WHERE rides.direction = %s 
          AND rides.campus = %s 
          AND rides.district = %s
          AND rides.seats > 0
    """, (filters["direction"], filters["campus"], filters["district"]))
    results = cur.fetchall()
    cur.close()
    conn.close()

    del user_data[chat_id]

    if len(results) == 0:
        bot.send_message(chat_id, "😔 Поездок по вашим параметрам не найдено. Попробуйте позже!")
        return

    bot.send_message(chat_id, f"🚗 Найдено поездок: {len(results)}")

    for ride in results:
        ride_id, driver_name, ride_time, seats, driver_tg_id = ride
        keyboard = types.InlineKeyboardMarkup()
        book_button = types.InlineKeyboardButton(text="📱 Забронировать", callback_data=f"book_{ride_id}")
        keyboard.add(book_button)
        bot.send_message(
            chat_id,
            f"Водитель: {driver_name} 🚘 🪑 {seats} мест\n⏰ {ride_time}",
            reply_markup=keyboard
        )


# ==========================================================
# ЕДИНЫЙ ОБРАБОТЧИК ВСЕХ CALLBACK-КНОПОК
# ==========================================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    # --- Кнопка "Отмена" — ловит нажатие с ЛЮБОГО шага ---
    if call.data == "cancel":
        bot.answer_callback_query(call.id)
        cancel_action(chat_id)
        return  # выходим сразу, дальше по функции идти не нужно

    # --- Выбор роли при регистрации ---
    elif call.data == "role_driver" or call.data == "role_passenger":
        if call.data == "role_driver":
            role = "driver"
        else:
            role = "passenger"
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📝 Отлично! Теперь введите ваше имя:")
        bot.register_next_step_handler(msg, save_name_handler, role)

    # --- Главное меню: создать поездку ---
    elif call.data == "menu_create_ride":
        bot.answer_callback_query(call.id)
        start_create_ride(chat_id)

    # --- Главное меню: найти поездку ---
    elif call.data == "menu_find_ride":
        bot.answer_callback_query(call.id)
        start_find_ride(chat_id)

    # --- Сценарий водителя: направление ---
    elif call.data == "dir_to_uni" or call.data == "dir_from_uni":
        bot.answer_callback_query(call.id)
        if call.data == "dir_to_uni":
            direction = "to_uni"
        else:
            direction = "from_uni"
        user_data[chat_id] = {"direction": direction}

        keyboard = types.InlineKeyboardMarkup()
        campus1_button = types.InlineKeyboardButton(text="🏫 Новокольцовский", callback_data="campus_novo")
        campus2_button = types.InlineKeyboardButton(text="🏛️ Старый (Мира)", callback_data="campus_mira")
        cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        keyboard.add(campus1_button, campus2_button)
        keyboard.add(cancel_button)
        bot.send_message(chat_id, "📍 В какой кампус?", reply_markup=keyboard)

    # --- Сценарий водителя: кампус ---
    elif call.data == "campus_novo" or call.data == "campus_mira":
        bot.answer_callback_query(call.id)
        if call.data == "campus_novo":
            campus = "novokolcovskiy"
        else:
            campus = "mira"
        user_data[chat_id]["campus"] = campus

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "📍 Откуда едете? (например: Ботаника, Уралмаш)", reply_markup=keyboard)
        bot.register_next_step_handler(msg, get_district_step, chat_id)

    # --- Сценарий пассажира: направление ---
    elif call.data == "find_dir_to_uni" or call.data == "find_dir_from_uni":
        bot.answer_callback_query(call.id)
        if call.data == "find_dir_to_uni":
            direction = "to_uni"
        else:
            direction = "from_uni"
        user_data[chat_id] = {"direction": direction}

        keyboard = types.InlineKeyboardMarkup()
        campus1_button = types.InlineKeyboardButton(text="🏫 Новокольцовский", callback_data="find_campus_novo")
        campus2_button = types.InlineKeyboardButton(text="🏛️ Старый (Мира)", callback_data="find_campus_mira")
        cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        keyboard.add(campus1_button, campus2_button)
        keyboard.add(cancel_button)
        bot.send_message(chat_id, "📍 Какой кампус?", reply_markup=keyboard)

    # --- Сценарий пассажира: кампус ---
    elif call.data == "find_campus_novo" or call.data == "find_campus_mira":
        bot.answer_callback_query(call.id)
        if call.data == "find_campus_novo":
            campus = "novokolcovskiy"
        else:
            campus = "mira"
        user_data[chat_id]["campus"] = campus

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "📍 Из какого вы района?", reply_markup=keyboard)
        bot.register_next_step_handler(msg, find_rides_step, chat_id)

    # --- Бронирование поездки ---
    elif call.data.startswith("book_"):
        bot.answer_callback_query(call.id, "Заявка отправлена!")
        ride_id = int(call.data.split("_")[1])

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT driver_tg_id, seats FROM rides WHERE id = %s", (ride_id,))
        ride_info = cur.fetchone()

        if ride_info is None:
            bot.send_message(chat_id, "⚠️ Эта поездка уже недоступна.")
            cur.close()
            conn.close()
            return

        driver_tg_id, seats = ride_info
        cur.execute("UPDATE rides SET seats = seats - 1 WHERE id = %s", (ride_id,))
        conn.commit()
        cur.close()
        conn.close()

        passenger_username = call.from_user.username
        bot.send_message(
            driver_tg_id,
            f"🔔 Новая заявка! Пассажир @{passenger_username} забронировал место."
        )
        bot.send_message(chat_id, "✅ Место забронировано! Водитель получил уведомление.")


# ==========================================================
# ЗАПУСК БОТА
# ==========================================================

bot.polling(none_stop=True)