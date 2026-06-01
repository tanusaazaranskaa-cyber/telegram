import asyncio
import os
import json
from collections import deque
from typing import Dict, Deque, List

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import aiohttp

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "google/gemini-2.0-flash-exp:free")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан!")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не задан!")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Хранилище контекста
user_contexts: Dict[int, Deque[Dict[str, str]]] = {}
MAX_CONTEXT_LENGTH = 10

def update_context(user_id: int, role: str, content: str):
    if user_id not in user_contexts:
        user_contexts[user_id] = deque(maxlen=MAX_CONTEXT_LENGTH)
    user_contexts[user_id].append({"role": role, "content": content})

def get_context_messages(user_id: int) -> List[Dict[str, str]]:
    if user_id not in user_contexts:
        return []
    return list(user_contexts[user_id])

def clear_context(user_id: int):
    if user_id in user_contexts:
        del user_contexts[user_id]

async def call_openrouter_api(messages: List[Dict[str, str]]) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/telegram-ai-bot",
        "X-Title": "Telegram AI Bot"
    }
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data["choices"][0]["message"]["content"]
            else:
                error_text = await response.text()
                return f" Ошибка API ({response.status}): {error_text[:200]}"

async def get_ai_response(user_id: int, user_message: str) -> str:
    try:
        update_context(user_id, "user", user_message)
        system_prompt = {"role": "system", "content": "Ты — полезный ассистент. Отвечай кратко на русском."}
        messages = [system_prompt] + get_context_messages(user_id)
        ai_reply = await call_openrouter_api(messages)
        update_context(user_id, "assistant", ai_reply)
        return ai_reply
    except Exception as e:
        return f" Ошибка: {str(e)}"

@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = f" Привет, {message.from_user.full_name}!\n\n"
    text += "Я AI-бот на OpenRouter.\n"
    text += "Задай мне любой вопрос!\n\n"
    text += "/clear — очистить историю\n"
    text += "/model — узнать модель"
    await message.answer(text)

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    clear_context(message.from_user.id)
    await message.answer(" История диалога очищена!")

@dp.message(Command("model"))
async def cmd_model(message: Message):
    await message.answer(f" Модель: <code>{AI_MODEL}</code>", parse_mode=ParseMode.HTML)

@dp.message()
async def handle_message(message: Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    response = await get_ai_response(message.from_user.id, message.text)
    await message.answer(response)

async def main():
    print("=" * 40)
    print(" Бот запущен!")
    print(f" Модель: {AI_MODEL}")
    print(f" Контекст: до {MAX_CONTEXT_LENGTH} сообщений")
    print("=" * 40)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
