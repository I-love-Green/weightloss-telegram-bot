import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from environs import Env

dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            weight REAL,
            tall REAL,
            age INTEGER
        )
    """)
    # --- таблиці для щоденника харчування ---
    cur.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        kcal REAL,
        protein REAL,
        fat REAL,
        carb REAL
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS food_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        product_id INTEGER,
        grams REAL,
        kcal REAL,
        protein REAL,
        fat REAL,
        carb REAL
    )''')

    conn.commit()
    conn.close()

def save_user(user_id, weight, tall, age):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO users (user_id, weight, tall, age)
        VALUES (?, ?, ?, ?)
    """, (user_id, weight, tall, age))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT weight, tall, age FROM users WHERE user_id = ?", (user_id,))
    data = cur.fetchone()
    conn.close()
    return data

class CaloriesForm(StatesGroup):
    weight = State()
    tall = State()
    age = State()

class AddMeal(StatesGroup):
    product = State()
    grams = State()

class AddProduct(StatesGroup):
    name = State()
    kcal = State()
    protein = State()
    fat = State()
    carb = State()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привіт! Я працюю на aiogram v3 🚀\nНапиши /help щоб подивитись опції.")

@dp.message(Command("help"))
async def command_help(message: Message):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Розрахунок калорій", callback_data="Calories")],
            [types.InlineKeyboardButton(text="Порада", callback_data="Advice")],
            [types.InlineKeyboardButton(text="Тренування", callback_data="Trainings")],
            [types.InlineKeyboardButton(text='Список спортивного обладнання', callback_data='ListSportEqupment')],
            [types.InlineKeyboardButton(text='Щоденник харчування', callback_data='FoodDiary')]
        ]
    )
    await message.answer("Обери що тобі потрібно:", reply_markup=kb)

@dp.callback_query(F.data == 'FoodDiary')
async def food_diary(call: CallbackQuery):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Додати продукт у базу", callback_data="AddProduct")],
            [types.InlineKeyboardButton(text="🍽 Додати прийом їжі", callback_data="AddMeal")],
            [types.InlineKeyboardButton(text="📊 Підсумок дня", callback_data="DaySummary")],
        ]
    )
    await call.message.answer("Щоденник харчування: обери дію ⬇️", reply_markup=kb)
    await call.answer()

# --- додавання продукту ---
@dp.callback_query(F.data == "AddProduct")
async def cb_add_product(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Введи назву продукту:")
    await state.set_state(AddProduct.name)
    await call.answer()

@dp.message(AddProduct.name)
async def add_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.lower())
    await message.answer("Ккал на 100г:")
    await state.set_state(AddProduct.kcal)

@dp.message(AddProduct.kcal)
async def add_product_kcal(message: Message, state: FSMContext):
    try:
        await state.update_data(kcal=float(message.text))
    except ValueError:
        await state.update_data(kcal=int(message.text))
    await message.answer("Білки на 100г:")
    await state.set_state(AddProduct.protein)

@dp.message(AddProduct.protein)
async def add_product_protein(message: Message, state: FSMContext):
    try:
        await state.update_data(protein=float(message.text))
    except ValueError:
        await state.update_data(protein=int(message.text))
    await message.answer("Жири на 100г:")
    await state.set_state(AddProduct.fat)

@dp.message(AddProduct.fat)
async def add_product_fat(message: Message, state: FSMContext):
    try:
        await state.update_data(fat=float(message.text))
    except ValueError:
        await state.update_data(fat=int(message.text))
    await message.answer("Вуглеводи на 100г:")
    await state.set_state(AddProduct.carb)

@dp.message(AddProduct.carb)
async def add_product_carb(message: Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO products (name, kcal, protein, fat, carb) VALUES (?, ?, ?, ?, ?)",
        (data["name"], data["kcal"], data["protein"], data["fat"], float(message.text)),
    )
    conn.commit()
    conn.close()
    await message.answer("✅ Продукт додано!")
    await state.clear()

# --- додавання прийому їжі ---
@dp.callback_query(F.data == "AddMeal")
async def cb_add_meal(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Введи назву продукту:")
    await state.set_state(AddMeal.product)
    await call.answer()

@dp.message(AddMeal.product)
async def meal_product(message: Message, state: FSMContext):
    await state.update_data(product=message.text.lower())
    await message.answer("Скільки грамів?")
    await state.set_state(AddMeal.grams)

@dp.message(AddMeal.grams)
async def meal_grams(message: Message, state: FSMContext):
    grams = float(message.text)
    data = await state.get_data()
    product_name = data["product"]

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE name=?", (product_name,))
    product = cur.fetchone()

    if not product:
        await message.answer("❌ Цього продукту нема в базі. Додай його через '➕ Додати продукт'.")
        await state.clear()
        conn.close()
        return

    product_id, name, kcal100, p100, f100, c100 = product
    kcal = kcal100 * grams / 100
    protein = p100 * grams / 100
    fat = f100 * grams / 100
    carb = c100 * grams / 100

    cur.execute(
        "INSERT INTO food_log (user_id, date, product_id, grams, kcal, protein, fat, carb) VALUES (?, DATE('now'), ?, ?, ?, ?, ?, ?)",
        (message.from_user.id, product_id, grams, kcal, protein, fat, carb),
    )
    conn.commit()
    conn.close()

    await message.answer(f"✅ Додано {grams} г {name} ({kcal:.1f} ккал, Б:{protein:.1f} Ж:{fat:.1f} В:{carb:.1f})")
    await state.clear()

# --- підсумок дня ---
@dp.callback_query(F.data == "DaySummary")
async def cb_day_summary(call: CallbackQuery):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT SUM(kcal), SUM(protein), SUM(fat), SUM(carb) FROM food_log WHERE user_id=? AND date=DATE('now')",
        (call.from_user.id,),
    )
    result = cur.fetchone()
    conn.close()

    if result and result[0]:
        kcal, p, f, c = result
        await call.message.answer(f"📊 Підсумок за сьогодні:\n"
                                  f"Калорії: {kcal:.1f}\n"
                                  f"Білки: {p:.1f} г\n"
                                  f"Жири: {f:.1f} г\n"
                                  f"Вуглеводи: {c:.1f} г")
    else:
        await call.message.answer("Ти ще нічого не додав сьогодні 🙂")
    await call.answer()


@dp.callback_query(F.data == "Calories")
async def callbacks_calories(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Введи свою вагу (кг):")
    await state.set_state(CaloriesForm.weight)
    await call.answer()

@dp.callback_query(F.data == "Advice")
async def callbacks_advice(call: CallbackQuery):
    await call.message.answer(
        "Головне в схудненні – це дефіцит калорій. Він утворюється або через менше споживання їжі, або через збільшення активності. Достатньо рухайся і харчуйся збалансовано!"
    )
    await call.answer()

@dp.callback_query(F.data == "Trainings")
async def callbacks_trainings(call: CallbackQuery):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Легке", callback_data="LiteTraining")],
            [types.InlineKeyboardButton(text="Силове", callback_data="PowerTraining")]
        ]
    )
    await call.message.answer("Обери тренування:", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "ListSportEqupment")
async def callbacks_equipment(call: CallbackQuery, state: FSMContext):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text='1. Скакалка', url='https://rozetka.com.ua/ua/322970512/p322970512/')],
            [types.InlineKeyboardButton(text='2. Еспандер', url='https://rozetka.com.ua/ua/322970539/p322970539/')],
            [types.InlineKeyboardButton(text='3. Ролик для преса', url='https://rozetka.com.ua/ua/395121630/p395121630/')],
            [types.InlineKeyboardButton(text='4. Дошка для віджимань', url='https://rozetka.com.ua/ua/425030877/p425030877/')],
            [types.InlineKeyboardButton(text='5. Фітнес гумки', url='https://rozetka.com.ua/ua/cornix-xr-0045/p366282078/')],
            [types.InlineKeyboardButton(text='6. Гантелі', url='https://rozetka.com.ua/ua/neo_sport_neo_g21k/p21155408/')],
        ]
    )
    await call.message.answer("Ось список потрібного, але не обов'язково необхідного спортивного обладнання: ", reply_markup=kb)
    await call.answer()
    await call.message.answer(
        'Скакалка — тренує витривалість і серцево-судинну систему, добре спалює калорії.\n'
        'Еспандер — розвиває силу рук, передпліччя і силу хвату.\n'
        'Ролик для преса — чудово тренує м’язи живота. Якщо робити вправи з колін — основне навантаження на прес.\n'
        'Дошка для віджимань — завдяки різним положенням ручок можна зміщувати акцент на груди, плечі чи трицепс.\n'
        'Фітнес-гумки — універсальні: підходять і для розминки, і для повноцінних тренувань. Допомагають збільшити навантаження.\n'
        'Гантелі — базовий снаряд для силових тренувань удома. Особливо потрібні для розвитку біцепсів і трицепсів.'
    )

@dp.callback_query(F.data == "LiteTraining")
async def send_gif_lite(call: CallbackQuery):
    await call.message.answer_animation(
        animation="https://media.giphy.com/media/Ju7l5y9osyymQ/giphy.gif",
        caption="Розминка для початку 🏃‍♂️"
    )
    await call.answer()

@dp.callback_query(F.data == "PowerTraining")
async def send_gif_power(call: CallbackQuery):
    await call.message.answer_animation(
        animation="https://gymbeam.cz/blog/wp-content/uploads/2021/10/01-pushup.gif",
        caption="Віджимання"
    )
    await call.answer()

# --- FSM: вага ---
@dp.message(CaloriesForm.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text)
    except ValueError:
        await message.answer("Введи число у кг!")
        return
    await state.update_data(weight=weight)
    await message.answer("Тепер введи свій зріст (см):")
    await state.set_state(CaloriesForm.tall)

# --- FSM: зріст ---
@dp.message(CaloriesForm.tall)
async def process_tall(message: Message, state: FSMContext):
    try:
        tall = float(message.text)
    except ValueError:
        await message.answer("Введи число у см!")
        return
    await state.update_data(tall=tall)
    await message.answer("Введи свій вік (років):")
    await state.set_state(CaloriesForm.age)

# --- FSM: вік + збереження в SQLite ---
@dp.message(CaloriesForm.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
    except ValueError:
        await message.answer("Введи число у роках!")
        return

    await state.update_data(age=age)
    data = await state.get_data()

    # ✅ Збереження в базу
    save_user(message.from_user.id, data["weight"], data["tall"], data["age"])

    # ✅ Розрахунок калорій
    calories = (10 * data["weight"]) + (6.25 * data["tall"]) - (5 * data["age"]) + 5
    protein = (calories * 0.3) / 4
    fat = (calories * 0.3) / 9
    carbs = (calories * 0.4) / 4

    await message.answer(f"📊 Твоя базова норма: {round(calories)} ккал/день")
    await message.answer(
        f"БЖВ:\n{round(protein)} г білків, {round(fat)} г жирів, {round(carbs)} г вуглеводів"
    )
    await state.clear()

@dp.message(Command("mydata"))
async def cmd_mydata(message: Message):
    data = get_user(message.from_user.id)
    if data:
        w, t, a = data
        await message.answer(f"📌 Твої дані:\nВага: {w} кг\nЗріст: {t} см\nВік: {a} років")
    else:
        await message.answer("❌ Дані ще не збережені. Використай /calories.")

# --- Запуск ---
async def main():
    env = Env()
    env.read_env(".env")
    bot = Bot(token=env('TOKEN'))
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())