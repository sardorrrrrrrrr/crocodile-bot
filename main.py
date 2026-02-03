import asyncio
import random
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats
from aiogram.exceptions import TelegramBadRequest

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('crocodile_game.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS scores 
                      (user_id INTEGER PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings 
                      (chat_id INTEGER PRIMARY KEY, lang TEXT)''')
    conn.commit()
    conn.close()

def update_score(user_id, name):
    conn = sqlite3.connect('crocodile_game.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO scores (user_id, name, score) VALUES (?, ?, 0)", (user_id, name))
    cursor.execute("UPDATE scores SET score = score + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_top_scores():
    conn = sqlite3.connect('crocodile_game.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, score FROM scores ORDER BY score DESC LIMIT 10")
    data = cursor.fetchall()
    conn.close()
    return data

def save_lang(chat_id, lang):
    conn = sqlite3.connect('crocodile_game.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (chat_id, lang) VALUES (?, ?)", (chat_id, lang))
    conn.commit()
    conn.close()

def load_lang(chat_id):
    conn = sqlite3.connect('crocodile_game.db')
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM settings WHERE chat_id = ?", (chat_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "🇺🇿 Uzb"

# --- O'YIN MA'LUMOTLARI ---
game_state = {}
LANG_DATA = {
    "🇺🇿 Uzb": {"start": "Yangi raund! Kim boshlovchi?", "be": "Boshlovchi bo'lish 🙋‍♂️", "change": "🔄 Almashtirish", "top_t": "🏆 Guruh reytingi:", "win": "🎉 G'alaba! {name} topdi. So'z: {word}", "words": ["Olma", "Kitob", "Mashina", "Qalam", "Quyosh", "Daryo"]},
    "🇷🇺 Rus": {"start": "Новый раунд! Кто ведущий?", "be": "Стать ведущим 🙋‍♂️", "change": "🔄 Сменить", "top_t": "🏆 Рейтинг:", "win": "🎉 Победа! {name} угадал. Слово: {word}", "words": ["Яблоко", "Книга", "Машина", "Карандаш", "Солнце", "Река"]},
    "🇺🇸 Eng": {"start": "New round! Who is the leader?", "be": "Become Leader 🙋‍♂️", "change": "🔄 Change", "top_t": "🏆 Ranking:", "win": "🎉 Victory! {name} guessed. Word: {word}", "words": ["Apple", "Book", "Car", "Pencil", "Sun", "River"]},
    "🇸🇦 Arab": {"start": "جولة جديدة! من القائد؟", "be": "كن قائدا 🙋‍♂️", "change": "🔄 تغيير", "top_t": "🏆 ترتيب:", "win": "🎉 فوز! {name} خمن. الكلمة: {word}", "words": ["تفاحة", "كتاب", "سيارة", "قلم", "شمس", "نهر"]},
    "🇹🇷 Tur": {"start": "Yeni tur! Lider kim?", "be": "Lider ol 🙋‍♂️", "change": "🔄 Değiştir", "top_t": "🏆 Sıralama:", "win": "🎉 Zafer! {name} bildi. Kelime: {word}", "words": ["Elma", "Kitap", "Araba", "Kalem", "Güneş", "Nehir"]}
}

# --- FUNKSIYALAR ---
async def set_main_menu(bot: Bot):
    # Faqat guruhlar uchun komandalar
    await bot.set_my_commands([
        BotCommand(command="start_game", description="🎮 O'yinni boshlash"), 
        BotCommand(command="top", description="🏆 Reyting")
    ], scope=BotCommandScopeAllGroupChats())

async def start_new_round(chat_id):
    lang = load_lang(chat_id)
    word = random.choice(LANG_DATA[lang]["words"]).lower()
    game_state[chat_id] = {"word": word, "leader": None, "msg_id": None}
    builder = InlineKeyboardBuilder()
    builder.button(text=LANG_DATA[lang]["be"], callback_data=f"be_leader_{chat_id}")
    sent = await bot.send_message(chat_id, LANG_DATA[lang]["start"], reply_markup=builder.as_markup())
    game_state[chat_id]["msg_id"] = sent.message_id

@dp.message(Command("start_game"))
async def choose_lang(message: types.Message):
    if message.chat.type == "private":
        return await message.answer("❌ Bu o'yin faqat guruhlarda ishlaydi! Botni guruhga qo'shing.")
    
    builder = InlineKeyboardBuilder()
    for lang in LANG_DATA.keys():
        builder.button(text=lang, callback_data=f"lang_{lang}")
    builder.adjust(3)
    await message.answer("🌍 Select Language / Tilni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    save_lang(callback.message.chat.id, lang)
    await callback.message.delete()
    await start_new_round(callback.message.chat.id)

@dp.callback_query(F.data.startswith("be_leader_") | F.data.startswith("change_"))
async def handle_leader(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    lang = load_lang(chat_id)
    
    if callback.data.startswith("change_") and callback.from_user.id != game_state[chat_id]["leader"]:
        return await callback.answer("❌ Faqat boshlovchi o'zgartira oladi!", show_alert=True)
    
    word = random.choice(LANG_DATA[lang]["words"]).lower()
    game_state[chat_id].update({"word": word, "leader": callback.from_user.id})
    
    await callback.answer(f"🤫 SO'Z: {word.upper()}", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    builder.button(text=LANG_DATA[lang]["change"], callback_data=f"change_{chat_id}")
    
    # Xatolikni oldini olish uchun try-except
    try:
        await callback.message.edit_text(
            f"🎮 Boshlovchi: {callback.from_user.full_name}\nSizning vazifangiz so'zni tushuntirish!", 
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        pass # Agar xabar o'zgarmasa, xatoni o'tkazib yuboramiz

@dp
