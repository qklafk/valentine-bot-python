import logging
from typing import Optional
from dotenv import load_dotenv
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Загружаем переменные окружения
load_dotenv()

# Включаем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация Bot и Dispatcher
BOT_TOKEN = os.getenv('BOT_TOKEN')
MINI_APP_URL = os.getenv('MINI_APP_URL', 'https://username.github.io/valentine-site')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# State группы для будущих функций
class QuizState(StatesGroup):
    waiting_for_answer = State()


# ==================== ФУНКЦИИ ====================

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Создает основную клавиатуру с кнопкой Mini App"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💌 Открыть сюрприз",
                    web_app=WebAppInfo(url=MINI_APP_URL)
                )
            ]
        ]
    )
    return keyboard


# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    first_name = message.from_user.first_name or "Малышка"
    
    welcome_text = (
        f"💕 Привет, {first_name}!\n\n"
        f"Я приготовил для тебя что-то очень милое на День Святого Валентина... 💘"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )
    
    logger.info(f"User {message.from_user.id} ({first_name}) started the bot")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "Вот что я умею:\n\n"
        "/start - Начать сначала\n"
        "/help - Эта справка\n"
        "/status - Статус бота\n\n"
        "Просто нажми на кнопку '💌 Открыть сюрприз' чтобы увидеть мое признание! 💕"
    )
    
    await message.answer(help_text)


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Обработчик команды /status"""
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    
    status_text = (
        f"✅ Бот работает!\n\n"
        f"👤 Твой ID: {user_id}\n"
        f"📝 Ник: @{username}\n"
        f"💕 Статус: Готов к признаниям!\n\n"
        f"Нажми кнопку ниже, чтобы открыть сюрприз 💌"
    )
    
    await message.answer(
        status_text,
        reply_markup=get_main_keyboard()
    )


# ==================== ОБРАБОТЧИКИ ТЕКСТА ====================

@dp.message(F.text.contains("люб"))
async def love_detector(message: types.Message):
    """Реагирует на текст со словом 'люб'"""
    response = (
        "И я тебя люблю! 💕\n\n"
        "Нажми кнопку ниже, чтобы увидеть сюрприз"
    )
    
    await message.answer(
        response,
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text.contains("ты мне"))
async def feelings_detector(message: types.Message):
    """Реагирует на текст 'ты мне'"""
    response = (
        "Ты - самый важный человек в моей жизни! 💕\n\n"
        "Открой сюрприз и узнаешь подробности 💌"
    )
    
    await message.answer(
        response,
        reply_markup=get_main_keyboard()
    )


@dp.message()
async def default_handler(message: types.Message):
    """Обработчик всех остальных сообщений"""
    response = (
        "Напиши /start и открой сюрприз! 💕\n"
        "Или используй /help для справки"
    )
    
    await message.answer(
        response,
        reply_markup=get_main_keyboard()
    )


# ==================== ОБРАБОТЧИК ERRORS ====================

async def error_handler(update: types.Update, exception: Exception):
    """Обработчик ошибок бота"""
    logger.error(f"Update {update}, caused error {exception}")
    
    # Пошлем сообщение об ошибке пользователю если возможно
    if update.message:
        try:
            await update.message.answer(
                "Произошла ошибка 😔\nПопробуй еще раз или используй /start"
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


# ==================== ЗАПУСК БОТА ====================

async def main():
    """Главная функция запуска"""
    logger.info("🤖 Бот запущен!")
    logger.info(f"Mini App URL: {MINI_APP_URL}")
    
    # Установка обработчика ошибок
    dp.error.register(error_handler)
    
    # Запуск polling'а
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
