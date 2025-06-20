# bot.py

from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F
import asyncio
import config
from database import (
    init_db,
    add_authorized_user,
    remove_authorized_user,
    get_all_authorized_users,
    add_request,
    update_response,
    get_request_by_id
)
import re

bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("BOT_TOKEN не установлен")

bot = Bot(token=bot_token)
dp = Dispatcher(storage=MemoryStorage())

# Клавиатура
kb_start = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Нужна заявка?")]], resize_keyboard=True)

kb_choice = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Оперативный картограф"), KeyboardButton(text="Радист")]],
    resize_keyboard=True
)

kb_operator_type = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="ОК"), KeyboardButton(text="Удаленный ОК")]],
    resize_keyboard=True
)

# Состояния
class RequestForm(StatesGroup):
    choice = State()         # Выбор между ОК и Радистом
    operator_type = State()  # Тип оператора (ОК / удаленный ОК)
    comment = State()        # Комментарий к заявке

def is_admin(user_id):
    return user_id in config.USER_ADMINS

def is_user_authorized(user_id):
    return user_id in config.USER_ADMINS or user_id in get_all_authorized_users()

@dp.startup()
async def on_startup():
    print("🔧 Инициализируем базу данных...")
    init_db()
    print("📦 База данных готова!")

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if not is_user_authorized(message.from_user.id):
        await message.answer("Вы не авторизованы для использования этого бота.")
        print(f"🚫 Пользователь {message.from_user.id} попытался использовать бота")
        return
    
    await state.clear()
    await message.answer("Здравствуйте!", reply_markup=kb_start)

@dp.message(F.text == "Нужна заявка?")
async def request_started(message: Message, state: FSMContext):
    await message.answer("Что вам нужно?", reply_markup=kb_choice)
    await state.set_state(RequestForm.choice)

@dp.message(RequestForm.choice)
async def handle_choice(message: Message, state: FSMContext):
    text = message.text.strip()
    if text not in ["Оперативный картограф", "Радист"]:
        await message.answer("Пожалуйста, выберите: Оперативный картограф или Радист")
        return

    await state.update_data(choice=text)
    if text == "Оперативный картограф":
        await message.answer("ОК или удаленный ОК?", reply_markup=kb_operator_type)
        await state.set_state(RequestForm.operator_type)
    else:
        await message.answer("Напишите ваше сообщение к заявке:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[]], resize_keyboard=True))
        await state.set_state(RequestForm.comment)

@dp.message(RequestForm.operator_type)
async def handle_operator_type(message: Message, state: FSMContext):
    text = message.text.strip()
    if text not in ["ОК", "Удаленный ОК"]:
        await message.answer("Пожалуйста, выберите: ОК или Удаленный ОК")
        return

    await state.update_data(operator_type=text)
    await message.answer("Напишите ваше сообщение к заявке:")
    await state.set_state(RequestForm.comment)

@dp.message(RequestForm.comment)
async def handle_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    data = await state.get_data()

    choice = data.get("choice")
    operator_type = data.get("operator_type")

    full_text = ""
    chat_type = ""
    chat_id = None

    if choice == "Оперативный картограф":
        full_text = f"Нужен оперативный картограф: {operator_type}"
        chat_id = config.CHAT_OK
        chat_type = "ok" if operator_type == "ОК" else "remote_ok"
    elif choice == "Радист":
        full_text = "Нужен радист"
        chat_id = config.CHAT_RADIO
        chat_type = "radio"

    if comment:
        full_text += f"\n\n{comment}"

    user_name = message.from_user.full_name
    user_id = message.from_user.id

    req_id = add_request(user_id, user_name, choice, operator_type or "Не нужен", chat_type, comment)

    sent = await bot.send_message(chat_id, f"Новый запрос #{req_id}:\n\n{full_text}")
    print(f"📨 Запрос #{req_id} отправлен в чат {chat_id}, ID сообщения: {sent.message_id}")

    await message.answer("✅ Заявка принята!", reply_markup=kb_start)
    await state.clear()

@dp.message(F.reply_to_message)
async def handle_group_response(message: Message):
    replied_to = message.reply_to_message
    if not replied_to.from_user.is_bot:
        return

    try:
        match = re.search(r"#(\d+)", replied_to.text)
        if match:
            req_id = int(match.group(1))
        else:
            return
    except Exception as e:
        print(f"❌ Ошибка парсинга req_id: {e}")
        return

    responder_username = message.from_user.username
    responder_name = message.from_user.full_name

    # Формируем ссылку на пользователя
    if responder_username:
        responder_link = f"https://t.me/{responder_username}" 
    else:
        responder_link = responder_name

    update_response(req_id, message.text, responder_name)

    request = get_request_by_id(req_id)
    if not request:
        return

    db_id, user_id, requester_name, ok_choice, radio_choice, chat_type, comment, response_text, responder_name = request

    # Отправляем ответ заявителю
    try:
        if chat_type in ["ok", "remote_ok"]:
            answer_text = f"✅ ОК нашёлся: {responder_link}\n\n"
        elif chat_type == "radio":
            answer_text = f"✅ Радист нашёлся: {responder_link}\n\n"
        else:
            answer_text = f"📬 Получен ответ: {responder_link}\n\n"

        await bot.send_message(user_id, answer_text)
        print(f"✅ Ответ на запрос #{req_id} отправлен пользователю {user_id}")

        # Отправляем откликнувшемуся — дублируем текст запроса и даём ссылку на профиль
        role = ok_choice if ok_choice and ok_choice != "Не нужен" else radio_choice
        chat_info = await bot.get_chat(user_id)
        username = chat_info.username

        profile_link = f"https://t.me/{username}"  if username else f"tg://user?id={user_id}"

        responder_text = (
            f"Вас просят помочь как {role}\n"
            f"Сообщение от заявителя:\n"
            f"{comment}\n\n"
            f"Профиль заявителя: {profile_link}"
        )

        await bot.send_message(message.from_user.id, responder_text)
        print(f"📩 Запрос переслан откликнувшемуся: {message.from_user.id}")

    except Exception as e:
        print(f"❌ Не удалось отправить ответ: {e}")

# Команда: /adduser 123456789
@dp.message(F.text.startswith("/adduser"))
async def add_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав на выполнение этой команды.")
        return

    try:
        new_user_id = int(message.text.split()[1])
        if is_user_authorized(new_user_id):
            await message.answer(f"⚠️ Пользователь {new_user_id} уже в списке")
            return

        add_authorized_user(new_user_id)
        await message.answer(f"✅ Пользователь {new_user_id} добавлен в список авторизованных")
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат команды. Используйте: /adduser 123456789")


# Команда: /removeuser 123456789
@dp.message(F.text.startswith("/removeuser"))
async def remove_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав на выполнение этой команды.")
        return

    try:
        user_id = int(message.text.split()[1])

        if user_id in config.USER_ADMINS:
            await message.answer("❌ Вы не можете удалить администратора из списка.")
            return

        if not is_user_authorized(user_id):
            await message.answer(f"❌ Пользователь {user_id} не найден в списке.")
            return

        remove_authorized_user(user_id)
        await message.answer(f"✅ Пользователь {user_id} удалён из списка авторизованных")
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат команды. Используйте: /removeuser 123456789")


# Запуск бота
async def main():
    print("🚀 Бот запущен и ожидает сообщений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
