import logging
from typing import Optional
from dotenv import load_dotenv
import os
from datetime import datetime
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from groq import Groq

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, CallbackQuery
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
MINI_APP_URL = os.getenv('MINI_APP_URL', 'https://qklafk.github.io/valentine-site/')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
RELATIONSHIP_START_DATE = os.getenv('RELATIONSHIP_START_DATE', '2025-12-01')
GIRLFRIEND_ID = int(os.getenv('GIRLFRIEND_ID', 0))
OWNER_ID = int(os.getenv('OWNER_ID', 0))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация Groq клиента
groq_client = Groq(api_key=GROQ_API_KEY)

# Инициализация scheduler для напоминаний
scheduler = AsyncIOScheduler()

# Хранилище активных пользователей (для срабатывания напоминаний)
active_users = set()

# State группы для будущих функций
class QuizState(StatesGroup):
    waiting_for_answer = State()


# ==================== ФУНКЦИИ ====================

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Создает основную клавиатуру с кнопкой Mini App и справкой"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💌 Открыть сюрприз",
                    web_app=WebAppInfo(url=MINI_APP_URL)
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Справка",
                    callback_data="help_callback"
                )
            ]
        ]
    )
    return keyboard


def get_days_together() -> tuple:
    """Подсчитывает количество дней, часов, минут и секунд в отношениях"""
    try:
        start_date = datetime.strptime(RELATIONSHIP_START_DATE, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        
        time_diff = now - start_date
        
        days = time_diff.days
        seconds = time_diff.seconds
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        return days, hours, minutes, secs
    except ValueError:
        logger.error(f"Неверный формат даты: {RELATIONSHIP_START_DATE}")
        return 0, 0, 0, 0


async def generate_confession() -> str:
    """Генерирует уникальное признание через Groq API"""
    try:
        message = groq_client.chat.completions.create(
            messages = [
                {
                    "role": "user",
                    "content": (
                        "Напиши короткое и искреннее признание в чувствах для девушки. "
                        "Это признание от Саши, написанное через тёплого телеграм-бота. "
                        "1–2 предложения максимум. Начни с имени (выбери либо 'Ира,', либо 'Иришка,'). "
                        "Имя должно быть ТОЛЬКО в начале и больше не повторяться. "
                        "Пиши простым, понятным языком, без цветистых слов, пафоса и лирики. "
                        "Говори о живых, реальных чувствах: почему она важна, что в ней ценят, "
                        "как спокойно и хорошо с ней. "
                        "Избегай штампов, метафор и обобщённых фраз. "
                        "Каждый раз генерируй новый, уникальный текст."
                    )
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.9,
            max_tokens=200,
        )
        
        confession = message.choices[0].message.content
        return confession
    except Exception as e:
        logger.error(f"Ошибка генерации признания: {e}")
        return "Ты для меня самая важная... 💕"



async def generate_chat_response(user_message: str) -> str:
    """Генерирует умный ответ на сообщение пользователя через ИИ"""
    try:
        system_prompt = (
            "Ты — телеграм-бот, созданный Сашей как тёплый подарок для его девушки Иры (Иришки). "
            "Ты не заменяешь Сашу, а мягко напоминаешь о нём и его заботе. "
            "Отвечай на сообщения Иры коротко, тепло и искренне, 1–2 предложениями. "
            "Будь добрым, внимательным и немного игривым, но без пафоса и давления. "
            "Иногда уместно упоминать Сашу как человека, который думает о ней и скучает, "
            "но не делай этого в каждом ответе. "
            "Если Ира пишет длинное сообщение — отвечай кратко и с любовью. 💕"
        )

        message = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.8,
            max_tokens=200,
        )
        
        return message.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка генерации ответа: {e}")
        return "Ты мне очень нравишься! 💕"


async def generate_reminder(reminder_type: str) -> str:
    """Генерирует напоминание через Groq API"""
    try:
        prompts = {
            "morning": (
                "Напиши короткое, тёплое утреннее сообщение для девушки по имени Ира (или Иришка). "
                "1–2 предложения максимум. Начни с её имени. "
                "Пожелай ей хорошего и спокойного дня, скажи что-то искренне приятное. "
                "Иногда уместно мягко напоминать, что Саша думает о ней или скучает, "
                "но не делай этого в каждом сообщении. "
                "Пиши просто, живо и без штампов. Каждый раз другой текст."
            ),
            "evening": (
                "Напиши короткое, нежное вечернее сообщение перед сном для девушки по имени Ира (или Иришка). "
                "1–2 предложения максимум. Начни с её имени. "
                "Пожелай ей спокойной ночи и тёплых снов, скажи что-то ласковое и поддерживающее. "
                "Иногда можно мягко упомянуть Сашу как человека, который с теплом думает о ней, "
                "но не делай этого слишком часто. "
                "Пиши просто и искренне, без пафоса и штампов. Каждый раз другой текст."
            )
        }

        message = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompts[reminder_type]}],
            model="llama-3.3-70b-versatile",
            temperature=0.85,
            max_tokens=150,
        )
        
        return message.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка генерации напоминания: {e}")
        if reminder_type == "morning":
            return "Доброе утро, Иришка! 🌅\nИмей чудесный день! Я думаю о тебе 💕"
        else:
            return "Спокойной ночи, Иришка! 🌙\nСладких снов тебе! 💕"


async def send_morning_reminder():
    """Отправляет утреннее напоминание"""
    if GIRLFRIEND_ID not in active_users:
        return
    
    reminder_text = await generate_reminder("morning")
    
    try:
        await bot.send_message(
            chat_id=GIRLFRIEND_ID,
            text=f"☀️ Утреннее напоминание:\n\n{reminder_text}"
        )
        logger.info(f"Утреннее напоминание отправлено Ире (ID: {GIRLFRIEND_ID})")
        
        # Отправляем копию владельцу для тестирования
        await bot.send_message(
            chat_id=OWNER_ID,
            text=f"📤 Отправлено Ире:\n☀️ Утреннее напоминание:\n\n{reminder_text}"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке утреннего напоминания: {e}")


async def send_evening_reminder():
    """Отправляет вечернее напоминание"""
    if GIRLFRIEND_ID not in active_users:
        return
    
    reminder_text = await generate_reminder("evening")
    
    try:
        await bot.send_message(
            chat_id=GIRLFRIEND_ID,
            text=f"🌙 Вечернее напоминание:\n\n{reminder_text}"
        )
        logger.info(f"Вечернее напоминание отправлено Ире (ID: {GIRLFRIEND_ID})")
        
        # Отправляем копию владельцу для тестирования
        await bot.send_message(
            chat_id=OWNER_ID,
            text=f"📤 Отправлено Ире:\n🌙 Вечернее напоминание:\n\n{reminder_text}"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке вечернего напоминания: {e}")


# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    first_name = message.from_user.first_name or "Иришка"
    user_id = message.from_user.id
    
    # Добавляем пользователя в активные (для напоминаний)
    if user_id == GIRLFRIEND_ID:
        active_users.add(GIRLFRIEND_ID)
        logger.info(f"Ира активирована для напоминаний")
    
    welcome_text = (
        f"💕 Привет, Иришка!\n\n"
        f"Я приготовил для тебя что-то на День Святого Валентина... 💘"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )
    
    logger.info(f"User {user_id} ({first_name}) started the bot")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "🎯 Вот что я умею:\n\n"
        "📱 Основное:\n"
        "💌 Открыть сюрприз\n\n"
        "⏱️ Команды:\n"
        "/days - Счетчик дней вместе (в днях, часах, секундах)\n"
        "/confession - Случайное признание (новое каждый раз)\n"
        "/help - Эта справка\n\n"
        "🎭 Дополнительно:\n"
        "Напиши мне что-нибудь - я отвечу! 💕"
    )
    
    await message.answer(help_text, reply_markup=get_main_keyboard())


@dp.callback_query(lambda c: c.data == "help_callback")
async def callback_help(callback_query: CallbackQuery):
    """Обработчик кнопки справки"""
    help_text = (
        "🎯 Вот что я умею:\n\n"
        "📱 Основное:\n"
        "💌 Открыть сюрприз\n\n"
        "⏱️ Команды:\n"
        "/days - Счетчик дней вместе (в днях, часах, секундах)\n"
        "/confession - Случайное признание (новое каждый раз)\n"
        "/help - Эта справка\n\n"
        "🎭 Дополнительно:\n"
        "Напиши мне что-нибудь - я отвечу! 💕"
    )
    
    await callback_query.message.edit_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="back_to_main"
                    )
                ]
            ]
        )
    )
    
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "back_to_main")
async def callback_back_to_main(callback_query: CallbackQuery):
    """Обработчик кнопки возврата в главное меню"""
    main_text = (
        f"💕 Привет, Иришка!\n\n"
        f"Я приготовил для тебя что-то на День Святого Валентина... 💘"
    )
    
    await callback_query.message.edit_text(
        main_text,
        reply_markup=get_main_keyboard()
    )
    
    await callback_query.answer()


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


@dp.message(Command("days"))
async def cmd_days(message: types.Message):
    """Обработчик команды /days - показывает счетчик дней в разных единицах"""
    days, hours, minutes, secs = get_days_together()
    
    # Вычисляем всё время в разных единицах
    total_hours = days * 24 + hours
    total_munutes = total_hours * 60 + minutes
    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + secs
    
    # Красивый формат для дней
    if days == 0:
        days_display = "0 (сегодня наш первый день!)"
    elif days == 1:
        days_display = "1"
    else:
        days_display = str(days)
    
    response = (
        f"💕 Мы вместе {days_display} дней\n"
        f"в часах это {total_hours} часов\n"
        f"в минутах это {total_munutes:,} минут\n"
        f"а в секундах целых {total_seconds:,}\n\n"
        f"Каждая секунда с тобой - волшебство ✨\n"
        f"Открой сюрприз, чтобы узнать, как сильно ты мне нужна 💌"
    )
    
    await message.answer(
        response,
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("confession"))
async def cmd_confession(message: types.Message):
    """Обработчик команды /confession - генерирует ИИ признание"""
    # Показываем индикатор печати
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    confession = await generate_confession()
    
    response = (
        f"💕 Вот что я хочу сказать:\n\n"
        f"{confession}\n\n"
        f"Посмотри полный сюрприз - нажми кнопку ниже 💌"
    )
    
    await message.answer(
        response,
        reply_markup=get_main_keyboard()
    )


# ==================== ОБРАБОТЧИКИ ТЕКСТА ====================

@dp.message()
async def default_handler(message: types.Message):
    """Обрабатывает любые сообщения с ИИ-ответом"""
    try:
        # Показываем статус "печатает"
        await bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )
        
        # Генерируем ответ через ИИ
        response = await generate_chat_response(message.text)
        
        # Отправляем ответ с клавиатурой
        await message.answer(
            response,
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в default_handler: {e}")
        await message.answer(
            "Что-то пошло не так... Напиши /help 💕",
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
    logger.info(f"Напоминания будут отправляться Ире (ID: {GIRLFRIEND_ID})")
    
    # Установка обработчика ошибок
    dp.error.register(error_handler)
    
    # Инициализация scheduler
    scheduler.start()
    
    # Настройка расписания для напоминаний
    # Утреннее напоминание: случайное время с 9:00 до 12:00
    morning_hour = random.randint(9, 11)
    morning_minute = random.randint(0, 59)
    scheduler.add_job(
        send_morning_reminder,
        CronTrigger(hour=morning_hour, minute=morning_minute),
        id='morning_reminder',
        name='Утреннее напоминание'
    )
    logger.info(f"⏰ Утреннее напоминание: {morning_hour:02d}:{morning_minute:02d}")
    
    # Вечернее напоминание: случайное время с 21:00 до 23:00
    evening_hour = random.randint(21, 22)
    evening_minute = random.randint(0, 59)
    scheduler.add_job(
        send_evening_reminder,
        CronTrigger(hour=evening_hour, minute=evening_minute),
        id='evening_reminder',
        name='Вечернее напоминание'
    )
    logger.info(f"⏰ Вечернее напоминание: {evening_hour:02d}:{evening_minute:02d}")
    
    # Запуск polling'а
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
