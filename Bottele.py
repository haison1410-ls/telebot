import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
from flask import Flask, request, Response
import threading

# --- 1. CẤU HÌNH ---
API_TOKEN = '8576826985:AAE3CkWqTN0q7FuqXpZsOQkfenRObAFNBK4'
ADMIN_GROUP_ID = -5260948214 
DB_NAME = 'helpdesk_v4.db'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
app = Flask('')

# --- 2. DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            user_id INTEGER,
            issue TEXT,
            status TEXT,
            handler_name TEXT,
            file_id TEXT,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 3. DASHBOARD WEB (FLASK) ---
def check_auth(username, password):
    return username == 'admin' and password == '123456'

def authenticate():
    return Response(
        'Vui lòng đăng nhập!', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

@app.route('/')
def dashboard():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()

    html = """
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Admin Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; padding: 20px; }
            .container { max-width: 1000px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h2 { color: #1a73e8; text-align: center; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f8f9fa; }
            .status-moi { color: #d93025; background: #fce8e6; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
            .status-xuly { color: #e37400; background: #fff4e5; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
            .status-xong { color: #188038; background: #e6f4ea; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🚀 DASHBOARD QUẢN LÝ TICKET</h2>
            <table>
                <tr><th>Thời gian</th><th>Yêu cầu</th><th>Trạng thái</th><th>Người đảm nhận</th></tr>
    """
    for row in rows:
        st = row['status']
        st_class = "status-moi" if st == "Mới" else ("status-xuly" if st == "Đang xử lý" else "status-xong")
        html += f"<tr><td>{row['timestamp']}</td><td>{row['issue']}</td><td><span class='{st_class}'>{st}</span></td><td>{row['handler_name']}</td></tr>"
    
    html += "</table></div></body></html>"
    return html

# --- 4. HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Chào mừng! Hãy gửi yêu cầu hoặc hình ảnh lỗi tại đây.")

@dp.message(F.chat.type == "private")
async def handle_user_request(message: Message):
    user_id = message.from_user.id
    content = message.text or message.caption or "[Hình ảnh]"
    file_id = message.photo[-1].file_id if message.photo else None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tickets (user_id, issue, status, handler_name, file_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)", 
                   (user_id, content, "Mới", "Chưa có", file_id, now))
    conn.commit()
    conn.close()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🙋‍♂️ Nhận ticket", callback_data=f"accept_{user_id}"))
    header = f"📩 **TICKET MỚI**\n👤: {message.from_user.full_name}\n🆔 ID: `{user_id}`"

    if file_id:
        await bot.send_photo(ADMIN_GROUP_ID, photo=file_id, caption=f"{header}\n📝: {content}", reply_markup=builder.as_markup())
    else:
        await bot.send_message(ADMIN_GROUP_ID, f"{header}\n📝: {content}", reply_markup=builder.as_markup())
    await message.answer("✅ Đã gửi yêu cầu tới đội ngũ kỹ thuật!")

@dp.callback_query(F.data.startswith("accept_"))
async def process_accept(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    admin_name = callback.from_user.full_name
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = ?, handler_name = ? WHERE user_id = ? AND status = ?", 
                   ("Đang xử lý", admin_name, user_id, "Mới"))
    conn.commit()
    conn.close()

    await bot.send_message(user_id, f"👨‍💻 {admin_name} đang xử lý yêu cầu của bạn!")
    builder = InlineKeyboardBuilder().row(InlineKeyboardButton(text="✅ Hoàn thành", callback_data=f"done_{user_id}"))
    
    text = (callback.message.text or callback.message.caption) + f"\n\n📌 **Đã nhận bởi:** {admin_name}"
    try:
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup())
    except: pass
    await callback.answer("Bạn đã nhận ticket!")

@dp.callback_query(F.data.startswith("done_"))
async def process_done(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = ? WHERE user_id = ?", ("Hoàn thành", user_id))
    conn.commit()
    conn.close()
    await bot.send_message(user_id, "✨ Yêu cầu của bạn đã hoàn thành!")
    await callback.answer("Đã đóng ticket!")

@dp.message(Command("report"))
async def send_report(message: Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status")
    stats = dict(cursor.fetchall())
    conn.close()
    msg = f"📊 **THỐNG KÊ**\n🆕 Mới: {stats.get('Mới', 0)}\n⏳ Đang xử lý: {stats.get('Đang xử lý', 0)}\n✅ Xong: {stats.get('Hoàn thành', 0)}"
    await message.answer(msg)

# --- 5. VẬN HÀNH ---
def run_web():
    app.run(host='0.0.0.0', port=8080)

async def main():
    threading.Thread(target=run_web, daemon=True).start()
    logging.info("Hệ thống đã sẵn sàng!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())