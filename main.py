# Импортируем библиотеку для работы с Telegram Bot API
import telebot
# Импортируем модуль для создания inline-кнопок
from telebot import types
# Импортируем библиотеку для работы с клавиатурами
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
# Импортируем библиотеку для подключения к PostgreSQL
import psycopg2
import os
import re
import math
import urllib.request
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Создаём экземпляр бота
bot = telebot.TeleBot(BOT_TOKEN)

# Глобальный словарь для хранения промежуточных данных пользователя
user_data = {}

# Словарь со списком микрорайонов и синонимов, сопоставленных с официальными округами
DISTRICT_ALIASES = {
    # Чкаловский
    "ботаника": "Чкаловский", "ботсад": "Чкаловский", "автовокзал": "Чкаловский",
    "уктус": "Чкаловский", "химаш": "Чкаловский", "химмаш": "Чкаловский",
    "чкаловский": "Чкаловский", "вторчермет": "Чкаловский", "втчм": "Чкаловский",
    "чермет": "Чкаловский", "елизавет": "Чкаловский", "солнечный": "Чкаловский",
    # Октябрьский
    "жби": "Октябрьский", "компрессорный": "Октябрьский", "компрессор": "Октябрьский",
    "синие камни": "Октябрьский", "синька": "Октябрьский", "птицефабрика": "Октябрьский",
    "октябрьский": "Октябрьский", "парковый": "Октябрьский", "кольцово": "Октябрьский",
    # Кировский
    "втузгородок": "Кировский", "втуз": "Кировский", "пионерский": "Кировский",
    "пионерка": "Кировский", "шарташ": "Кировский", "упи": "Кировский",
    "кировский": "Кировский", "изоплит": "Кировский", "калиновский": "Кировский",
    # Орджоникидзевский
    "уралмаш": "Орджоникидзевский", "эльмаш": "Орджоникидзевский",
    "орджоникидзевский": "Орджоникидзевский",
    # Верх-Исетский
    "виз": "Верх-Исетский", "верх-исетский": "Верх-Исетский", "заречный": "Верх-Исетский",
    "заречка": "Верх-Исетский", "зарик": "Верх-Исетский", "широкая речка": "Верх-Исетский",
    "мичуринский": "Верх-Исетский", "верхисет": "Верх-Исетский", "вис": "Верх-Исетский", "верх исетский": "Верх-Исетский", "верх-исет": "Верх-Исетский",
    # Железнодорожный
    "вокзал": "Железнодорожный", "железнодорожный": "Железнодорожный", "жд": "Железнодорожный",
    "вокзальный": "Железнодорожный", "сортировка": "Железнодорожный",
    "завокзальный": "Железнодорожный", "семь ключей": "Железнодорожный",
    # Ленинский
    "центр": "Ленинский", "ленинский": "Ленинский", "юго-западный": "Ленинский",
    "юго западный": "Ленинский", "юго-запад": "Ленинский", "московская горка": "Ленинский",
    # Академический
    "академический": "Академический", "академ": "Академический",
    "краснолесье": "Академический", "унц": "Академический"
}

# Координаты центров округов для резервного расчета расстояния
DISTRICT_COORDS = {
    "Чкаловский": (56.766, 60.623),
    "Октябрьский": (56.816, 60.716),
    "Кировский": (56.845, 60.645),
    "Орджоникидзевский": (56.892, 60.612),
    "Верх-Исетский": (56.827, 60.545),
    "Железнодорожный": (56.866, 60.550),
    "Ленинский": (56.815, 60.585),
    "Академический": (56.788, 60.531)
}


def get_official_district(text):
    return DISTRICT_ALIASES.get(text.strip().lower())


def calculate_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return 9999.0
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return r * c


def get_nearest_district(lat, lon):
    if None in (lat, lon):
        return None

    ekb_center_lat, ekb_center_lon = 56.838, 60.597

    if calculate_distance(lat, lon, ekb_center_lat, ekb_center_lon) > 60.0:
        return None

    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=ru"
    req = urllib.request.Request(url, headers={'User-Agent': 'UrFU-Carpool-Bot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            address = data.get('address', {})

            area_names = [
                address.get('city_district', ''),
                address.get('suburb', ''),
                address.get('borough', ''),
                address.get('neighbourhood', '')
            ]

            for area in area_names:
                if not area: continue
                clean_area = area.lower().replace("район", "").replace("микрорайон", "").strip()
                for alias, official in DISTRICT_ALIASES.items():
                    if alias in clean_area:
                        return official
    except Exception as e:
        print(f"Ошибка геокодера OSM: {e}")

    min_dist = float('inf')
    nearest = None
    for district, (d_lat, d_lon) in DISTRICT_COORDS.items():
        dist = calculate_distance(lat, lon, d_lat, d_lon)
        if dist < min_dist:
            min_dist = dist
            nearest = district
    return nearest


def is_valid_time(text):
    match = re.match(r'^(\d{1,2}):(\d{2})$', text.strip())
    if not match:
        return False
    hours = int(match.group(1))
    minutes = int(match.group(2))
    if hours < 0 or hours > 23:
        return False
    if minutes < 0 or minutes > 59:
        return False
    return True


# ==========================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
# ==========================================================
def get_db_connection():
    conn = psycopg2.connect(
        host="db",
        database=os.getenv("POSTGRES_DB", "urfu_poputka"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD")
    )
    return conn


# ==========================================================
# ОБЩИЙ ОБРАБОТЧИК ОТМЕНЫ ДЕЙСТВИЯ
# ==========================================================
def cancel_action(chat_id):
    if chat_id in user_data:
        del user_data[chat_id]
    bot.clear_step_handler_by_chat_id(chat_id)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    name = result[0] if result is not None else "пользователь"
    show_main_menu(chat_id, name, greet=False)


# ==========================================================
# ГЛАВНОЕ МЕНЮ И РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ
# ==========================================================
def show_main_menu(chat_id, name, greet=True):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM rides WHERE driver_tg_id = %s", (chat_id,))
    active_ride = cur.fetchone()
    cur.close()
    conn.close()

    keyboard = types.InlineKeyboardMarkup()
    create_ride_button = types.InlineKeyboardButton(text="🚘 Создать поездку", callback_data="menu_create_ride")
    find_ride_button = types.InlineKeyboardButton(text="🚶 Найти поездку", callback_data="menu_find_ride")
    restart_button = types.InlineKeyboardButton(text="🔄 Начать сначала", callback_data="restart")

    keyboard.add(create_ride_button, find_ride_button)

    if active_ride:
        delete_button = types.InlineKeyboardButton(text="🗑 Удалить мою поездку", callback_data="delete_my_ride")
        keyboard.add(delete_button)

    keyboard.add(restart_button)

    if greet:
        text = f"👋 Привет, {name}!\nЧто хотите сделать?"
    else:
        text = "Что хотите сделать?"
    bot.send_message(chat_id, text, reply_markup=keyboard)


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
        msg = bot.send_message(
            chat_id,
            "🚗 Добро пожаловать в УрФУ-Попутку!\n📝 Пожалуйста, введите ваше имя:"
        )
        bot.register_next_step_handler(msg, save_name_handler)


def save_name_handler(message):
    chat_id = message.chat.id
    name = message.text.strip().capitalize()
    if not name or len(name) < 2:
        msg = bot.send_message(chat_id,
                               "⚠️ Имя должно содержать хотя бы 2 символа. Пожалуйста, введите корректное имя:")
        bot.register_next_step_handler(msg, save_name_handler)
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (tg_id, name, role, rating_driver, rating_passenger)
        VALUES (%s, %s, %s, 5.0, 5.0)
        ON CONFLICT (tg_id) DO UPDATE 
        SET name = EXCLUDED.name
    """, (chat_id, name, "user"))
    conn.commit()
    cur.close()
    conn.close()

    show_main_menu(chat_id, name, greet=True)


# ==========================================================
# ОБРАБОТКА ГЕОПОЗИЦИИ И ТЕКСТОВОГО ВВОДА
# ==========================================================
def request_location_or_text(chat_id, prompt_text, is_driver):
    bot.clear_step_handler_by_chat_id(chat_id)
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton(text="📍 Отправить геопозицию", request_location=True))
    keyboard.add(KeyboardButton(text="❌ Отмена"))
    msg = bot.send_message(chat_id, prompt_text, reply_markup=keyboard)
    bot.register_next_step_handler(msg, get_location_step, chat_id, is_driver)


def get_location_step(message, chat_id, is_driver=True):
    if message.content_type == 'text' and message.text and ("отмена" in message.text.lower() or "❌" in message.text):
        bot.send_message(chat_id, "Действие отменено.", reply_markup=ReplyKeyboardRemove())
        cancel_action(chat_id)
        return

    if chat_id not in user_data:
        user_data[chat_id] = {}

    if message.content_type == 'location' or message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        nearest = get_nearest_district(lat, lon)

        user_data[chat_id]["lat"] = lat
        user_data[chat_id]["lon"] = lon
        user_data[chat_id]["district"] = nearest

        if nearest:
            bot.send_message(chat_id, f"📍 Район определен: {nearest}",
                             reply_markup=ReplyKeyboardRemove())
        else:
            bot.send_message(chat_id,
                             "📍 Координаты получены, но точный район определить не удалось (или вы слишком далеко от Екатеринбурга).",
                             reply_markup=ReplyKeyboardRemove())

    elif message.content_type == 'text' and message.text:
        district = get_official_district(message.text)
        if not district:
            msg = bot.send_message(chat_id,
                                   "⚠️ Район не распознан. Пожалуйста, проверьте название или отправьте геопозицию:")
            bot.register_next_step_handler(msg, get_location_step, chat_id, is_driver)
            return
        user_data[chat_id]["district"] = district
        user_data[chat_id]["lat"] = None
        user_data[chat_id]["lon"] = None
        bot.send_message(chat_id, f"📍 Район определен: {district}", reply_markup=ReplyKeyboardRemove())
    else:
        msg = bot.send_message(chat_id, "⚠️ Пожалуйста, отправьте текстовое название района или геопозицию.")
        bot.register_next_step_handler(msg, get_location_step, chat_id, is_driver)
        return

    if is_driver:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "⏰ Укажите время выезда (формат ЧЧ:ММ, например: 08:30):",
                               reply_markup=keyboard)
        bot.register_next_step_handler(msg, get_time_step, chat_id)
    else:
        execute_ride_search(chat_id)


# ==========================================================
# СОЗДАНИЕ ПОЕЗДКИ (ВОДИТЕЛЬ)
# ==========================================================
def start_create_ride(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    to_uni_button = types.InlineKeyboardButton(text="🏫 В ВУЗ", callback_data="dir_to_uni")
    from_uni_button = types.InlineKeyboardButton(text="🏠 ИЗ ВУЗА", callback_data="dir_from_uni")
    cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    keyboard.add(to_uni_button, from_uni_button)
    keyboard.add(cancel_button)
    bot.send_message(chat_id, "🧭 Направление поездки:", reply_markup=keyboard)


def get_time_step(message, chat_id):
    time_str = message.text
    if not time_str or not is_valid_time(time_str):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(
            chat_id,
            "⚠️ Некорректный формат времени. Пожалуйста, используйте формат ЧЧ:ММ.",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(msg, get_time_step, chat_id)
        return

    user_data[chat_id]["time"] = time_str
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    msg = bot.send_message(chat_id, "🪑 Укажите количество свободных мест (от 1 до 4):", reply_markup=keyboard)
    bot.register_next_step_handler(msg, get_seats_step, chat_id)


def get_seats_step(message, chat_id):
    try:
        seats = int(message.text)
    except (ValueError, TypeError):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "⚠️ Ошибка ввода. Пожалуйста, введите число (например, 3):",
                               reply_markup=keyboard)
        bot.register_next_step_handler(msg, get_seats_step, chat_id)
        return

    if seats < 1 or seats > 4:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "⚠️ Допустимое количество мест: от 1 до 4.", reply_markup=keyboard)
        bot.register_next_step_handler(msg, get_seats_step, chat_id)
        return

    user_data[chat_id]["seats"] = seats
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    msg = bot.send_message(chat_id, "💰 Укажите стоимость одного места (в рублях):", reply_markup=keyboard)
    bot.register_next_step_handler(msg, get_price_step, chat_id)


def get_price_step(message, chat_id):
    try:
        price = int(message.text)
    except (ValueError, TypeError):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "⚠️ Ошибка ввода. Пожалуйста, введите число:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, get_price_step, chat_id)
        return

    if price < 0 or price > 10000:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
        msg = bot.send_message(chat_id, "⚠️ Укажите стоимость от 0 до 10000 рублей:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, get_price_step, chat_id)
        return

    user_data[chat_id]["price"] = price
    ride = user_data[chat_id]

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM rides WHERE driver_tg_id = %s", (chat_id,))

        cur.execute("""
                INSERT INTO rides (driver_tg_id, direction, campus, district, lat, lon, time, seats, price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (chat_id, ride["direction"], ride["campus"], ride.get("district"), ride.get("lat"), ride.get("lon"),
                  ride["time"], ride["seats"], ride["price"]))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        bot.send_message(
            chat_id,
            "⚠️ Произошла ошибка при сохранении данных. Пожалуйста, повторите попытку позже."
        )
        print(f"Ошибка базы данных при создании поездки: {e}")
        return

    direction_text = "В ВУЗ" if ride["direction"] == "to_uni" else "ИЗ ВУЗА"
    campus_text = "Новокольцовский" if ride["campus"] == "novokolcovskiy" else "Старый (Мира)"
    district_info = ride.get("district") if ride.get("district") else "по геопозиции"

    bot.send_message(
        chat_id,
        f"✅ Поездка успешно создана!\n"
        f"🧭 {direction_text}  📍 {district_info} → {campus_text}\n"
        f"⏰ {ride['time']}  🪑 Свободных мест: {ride['seats']}  💰 {ride['price']} руб."
    )


# ==========================================================
# ПОИСК И БРОНИРОВАНИЕ ПОЕЗДКИ (ПАССАЖИР)
# ==========================================================
def start_find_ride(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    to_uni_button = types.InlineKeyboardButton(text="🏫 В ВУЗ", callback_data="find_dir_to_uni")
    from_uni_button = types.InlineKeyboardButton(text="🏠 ИЗ ВУЗА", callback_data="find_dir_from_uni")
    cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    keyboard.add(to_uni_button, from_uni_button)
    keyboard.add(cancel_button)
    bot.send_message(chat_id, "🧭 Выберите направление:", reply_markup=keyboard)


def execute_ride_search(chat_id):
    filters = user_data[chat_id]
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT rides.id, users.name, users.rating_driver, rides.time, rides.seats, rides.price, rides.driver_tg_id, rides.district, rides.lat, rides.lon, COALESCE(users.reviews_count, 0)
        FROM rides
        JOIN users ON rides.driver_tg_id = users.tg_id
        WHERE rides.direction = %s 
          AND rides.campus = %s 
          AND rides.seats > 0
          AND rides.driver_tg_id != %s
    """, (filters["direction"], filters["campus"], chat_id))

    all_rides = cur.fetchall()
    cur.close()
    conn.close()
    del user_data[chat_id]

    valid_rides = []
    for r in all_rides:
        r_id, d_name, d_rating, r_time, r_seats, r_price, d_tg_id, r_dist, r_lat, r_lon, d_reviews = r

        if filters.get("district") is not None and r_dist == filters["district"]:
            valid_rides.append(r)

    if not valid_rides:
        menu_keyboard = types.InlineKeyboardMarkup()
        menu_keyboard.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu"))
        bot.send_message(
            chat_id,
            "😔 Актуальных поездок по вашим критериям не найдено.",
            reply_markup=menu_keyboard
        )
        return

    bot.send_message(chat_id, f"🚗 Найдено доступных поездок: {len(valid_rides)}")

    for r in valid_rides:
        r_id, d_name, d_rating, r_time, r_seats, r_price, d_tg_id, r_dist, r_lat, r_lon, d_reviews = r

        keyboard = types.InlineKeyboardMarkup()
        book_button = types.InlineKeyboardButton(text="📱 Забронировать", callback_data=f"book_{r_id}")
        menu_button = types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")

        keyboard.add(book_button)
        keyboard.add(menu_button)

        if d_reviews == 0:
            rating_display = f"{d_name} (нет оценок)"
        else:
            rating_display = f"{d_name} ⭐ {float(d_rating):.1f} ({d_reviews} оценок)"

        bot.send_message(
            chat_id,
            f"Водитель: {rating_display} 🚘\n🪑 Доступно мест: {r_seats} | 💰 {r_price} руб.\n⏰ Время выезда: {r_time}",
            reply_markup=keyboard
        )


# ==========================================================
# ОБРАБОТКА CALLBACK-ЗАПРОСОВ
# ==========================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    if call.data == "cancel":
        bot.answer_callback_query(call.id)
        cancel_action(chat_id)
        return
    elif call.data == "back_to_menu":
        bot.answer_callback_query(call.id)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        name = result[0] if result is not None else "пользователь"
        show_main_menu(chat_id, name, greet=False)
        return
    elif call.data == "restart":
        bot.answer_callback_query(call.id)
        if chat_id in user_data:
            del user_data[chat_id]
        bot.clear_step_handler_by_chat_id(chat_id)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        name = result[0] if result is not None else "пользователь"
        show_main_menu(chat_id, name, greet=True)
        return

    elif call.data == "menu_create_ride":
        bot.answer_callback_query(call.id)
        start_create_ride(chat_id)

    elif call.data == "delete_my_ride":
        bot.answer_callback_query(call.id)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM rides WHERE driver_tg_id = %s", (chat_id,))
        conn.commit()

        cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        name = result[0] if result is not None else "пользователь"

        bot.send_message(chat_id, "🗑 Ваша поездка успешно удалена.")
        show_main_menu(chat_id, name, greet=False)
        return

    elif call.data == "menu_find_ride":
        bot.answer_callback_query(call.id)
        start_find_ride(chat_id)

    elif call.data == "dir_to_uni" or call.data == "dir_from_uni":
        bot.answer_callback_query(call.id)
        direction = "to_uni" if call.data == "dir_to_uni" else "from_uni"
        user_data[chat_id] = {"direction": direction}

        keyboard = types.InlineKeyboardMarkup()
        campus1_button = types.InlineKeyboardButton(text="🏫 Новокольцовский", callback_data="campus_novo")
        campus2_button = types.InlineKeyboardButton(text="🏛️ Старый (Мира)", callback_data="campus_mira")
        cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        keyboard.add(campus1_button, campus2_button)
        keyboard.add(cancel_button)
        bot.send_message(chat_id, "📍 Укажите целевой кампус:", reply_markup=keyboard)

    elif call.data == "campus_novo" or call.data == "campus_mira":
        bot.answer_callback_query(call.id)
        campus = "novokolcovskiy" if call.data == "campus_novo" else "mira"

        if chat_id not in user_data:
            user_data[chat_id] = {}
        user_data[chat_id]["campus"] = campus

        request_location_or_text(
            chat_id,
            "📍 Введите название района (например: ЖБИ, Уралмаш) ИЛИ используйте кнопку отправки геопозиции:",
            is_driver=True
        )

    elif call.data == "find_dir_to_uni" or call.data == "find_dir_from_uni":
        bot.answer_callback_query(call.id)
        direction = "to_uni" if call.data == "find_dir_to_uni" else "from_uni"
        user_data[chat_id] = {"direction": direction}

        keyboard = types.InlineKeyboardMarkup()
        campus1_button = types.InlineKeyboardButton(text="🏫 Новокольцовский", callback_data="find_campus_novo")
        campus2_button = types.InlineKeyboardButton(text="🏛️ Старый (Мира)", callback_data="find_campus_mira")
        cancel_button = types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        keyboard.add(campus1_button, campus2_button)
        keyboard.add(cancel_button)
        bot.send_message(chat_id, "📍 Выберите кампус:", reply_markup=keyboard)

    elif call.data == "find_campus_novo" or call.data == "find_campus_mira":
        bot.answer_callback_query(call.id)
        campus = "novokolcovskiy" if call.data == "find_campus_novo" else "mira"

        if chat_id not in user_data:
            user_data[chat_id] = {}
        user_data[chat_id]["campus"] = campus

        request_location_or_text(
            chat_id,
            "📍 Укажите район отправления или отправьте геопозицию:",
            is_driver=False
        )


    elif call.data.startswith("finish_ride_"):
        bot.answer_callback_query(call.id, "Поездка завершена.")
        passenger_tg_id = int(call.data.split("_")[2])
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM rides WHERE driver_tg_id = %s", (chat_id,))
        conn.commit()  # <--- вот это забыли
        cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
        driver_res = cur.fetchone()
        driver_name = driver_res[0] if driver_res is not None else "Водитель"
        cur.execute("SELECT name FROM users WHERE tg_id = %s", (passenger_tg_id,))
        pass_res = cur.fetchone()
        pass_name = pass_res[0] if pass_res is not None else "пассажир"
        cur.close()
        conn.close()

        # Редактируем сообщение с кнопкой завершения, убирая инлайн-клавиатуру и показывая статус

        bot.edit_message_text(
            "🏁 Вы завершили поездку.",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        # Выводим главное меню ровно один раз

        show_main_menu(chat_id, driver_name, greet=False)

        # Отправляем пассажиру предложение оценить водителя с кнопкой пропуска

        rate_kb = types.InlineKeyboardMarkup(row_width=5)
        rate_btns = [types.InlineKeyboardButton(text=f"{i}⭐", callback_data=f"rate_{chat_id}_{i}") for i in range(1, 6)]
        rate_kb.add(*rate_btns)
        skip_btn = types.InlineKeyboardButton(text="Пропустить", callback_data=f"skip_rate_{chat_id}")
        rate_kb.add(skip_btn)
        bot.send_message(
            passenger_tg_id,
            f"🏁 Водитель {driver_name} завершил поездку.\n\nПожалуйста, оцените водителя:",
            reply_markup=rate_kb
        )

        return

    elif call.data.startswith("skip_rate_"):
        bot.answer_callback_query(call.id, "Оценка пропущена.")
        driver_tg_id = int(call.data.split("_")[2])

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
        res = cur.fetchone()
        pass_name = res[0] if res is not None else "пользователь"
        cur.close()
        conn.close()

        bot.edit_message_text(
            "👍 Поездка завершена. Спасибо!",
            chat_id=chat_id,
            message_id=call.message.message_id
        )
        show_main_menu(chat_id, pass_name, greet=False)
        return

    elif call.data.startswith("rate_"):
        parts = call.data.split("_")
        driver_tg_id = int(parts[1])
        score = int(parts[2])

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT rating_driver, COALESCE(reviews_count, 0) FROM users WHERE tg_id = %s", (driver_tg_id,))
        res = cur.fetchone()

        if res:
            current_rating = float(res[0])
            reviews_count = int(res[1])

            if reviews_count == 0:
                new_rating = score
            else:
                new_rating = round(((current_rating * reviews_count) + score) / (reviews_count + 1), 2)

            new_count = reviews_count + 1

            cur.execute("UPDATE users SET rating_driver = %s, reviews_count = %s WHERE tg_id = %s",
                        (new_rating, new_count, driver_tg_id))
            conn.commit()

        cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
        pass_res = cur.fetchone()
        pass_name = pass_res[0] if pass_res is not None else "пользователь"

        cur.close()
        conn.close()

        bot.edit_message_text(
            f"✅ Благодарим за обратную связь! Ваша оценка ({score}⭐) успешно сохранена.",
            chat_id=chat_id,
            message_id=call.message.message_id
        )

        bot.send_message(
            driver_tg_id,
            f"🏁 Поездка с пассажиром {pass_name} успешно завершена."
        )

        show_main_menu(chat_id, pass_name, greet=False)
        return

    elif call.data.startswith("book_"):
        bot.answer_callback_query(call.id, "Заявка успешно отправлена.")
        ride_id = int(call.data.split("_")[1])

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT driver_tg_id, seats FROM rides WHERE id = %s", (ride_id,))
        ride_info = cur.fetchone()

        if ride_info is None:
            bot.send_message(chat_id, "⚠️ Выбранная поездка более недоступна.")
            cur.close()
            conn.close()
            return

        driver_tg_id, seats = ride_info

        # Уменьшаем количество мест или удаляем, если место последнее
        if seats <= 1:
            cur.execute("DELETE FROM rides WHERE id = %s", (ride_id,))
        else:
            cur.execute("UPDATE rides SET seats = seats - 1 WHERE id = %s", (ride_id,))
        conn.commit()

        cur.execute("SELECT name FROM users WHERE tg_id = %s", (chat_id,))
        passenger_result = cur.fetchone()
        passenger_name = passenger_result[0] if passenger_result is not None else "пользователь"

        cur.execute("SELECT name FROM users WHERE tg_id = %s", (driver_tg_id,))
        driver_result = cur.fetchone()
        driver_name = driver_result[0] if driver_result is not None else "Водитель"
        cur.close()
        conn.close()

        passenger_username = f"@{call.from_user.username}" if call.from_user.username else "скрытый_пользователь"

        # Кнопка для завершения поездки водителем
        finish_kb = types.InlineKeyboardMarkup()
        finish_btn = types.InlineKeyboardButton(text="🏁 Завершить поездку", callback_data=f"finish_ride_{chat_id}")
        finish_kb.add(finish_btn)

        bot.send_message(
            driver_tg_id,
            f"🔔 Поступила новая заявка! Пассажир {passenger_username} ({passenger_name}) забронировал место в вашей поездке.",
            reply_markup=finish_kb
        )

        # show_main_menu(driver_tg_id, driver_name, greet=False)

        bot.send_message(
            chat_id,
            "✅ Бронирование подтверждено! Водитель проинформирован. Ожидайте поездку."
        )


# ==========================================================
# ЗАПУСК БОТА
# ==========================================================
if __name__ == '__main__':
    bot.polling(none_stop=True)
