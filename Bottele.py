import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
from flask import Flask
import threading

# --- 1. CẤU HÌNH ---
API_TOKEN = '8576826985:AAE3CkWqTN0q7FuqXpZsOQkfenRObAFNBK4'
ADMIN_GROUP_ID = -5260948214 
DB_NAME = 'helpdesk_v4.db' # Đổi sang v4 để cập nhật cấu hình mới nhất

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
@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()

    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Admin Helpdesk Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f7f6; padding: 20px; }
            h2 { color: #333; text-align: center; }
            table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 5px 15px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
            th, td { padding: 15px; text-align: left; border-bottom: 1px solid #eee; }
            th { background: #007bff; color: white; }
            .status-moi { background: #ff4757; color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px; }
            .status-xuly { background: #ffa502; color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px; }
            .status-xong { background: #2ed573; color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px; }
            tr:hover { background: #f1f1f1; }
        </style>
    </head>
    <body>
        <h2>🚀 HỆ THỐNG QUẢN LÝ TICKET</h2>
        <table>
            <tr>
                <th>Thời gian</th>
                <th>User ID</th>
                <th>Nội dung / File</th>
                <th>Trạng thái</th>
                <th>Người xử lý</th>
            </tr>
    """
    for row in rows:
        st_class = "status-moi" if row['status'] == "Mới" else ("status-xuly" if row['status'] == "Đang xử lý" else "status-xong")
        html += f"""
            <tr>
                <td>{row['timestamp']}</td>
                <td>{row['user_id']}</td>
                <td>{row['issue']}</td>
                <td><span class="{st_class}">{row['status']}</span></td>
                <td>{row['handler_name'] or '---'}</td>
            </tr>
        """
    html += "</table></body></html>"
    return html

# --- 4. HÀM THỐNG KÊ (REPORT) ---
def get_daily_report():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Mới'")
        new = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Đang xử lý'")
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Hoàn thành'")
        done = cursor.fetchone()[0]
        conn.close()
        return f"📊 **THỐNG KÊ**\n🆕 Mới: {new}\n⏳ Đang xử lý: {pending}\n✅ Xong: {done}"
    except: return "❌ Lỗi đọc DB"

# --- 5. HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Chào bạn! Hãy gửi nội dung hoặc hình ảnh cần hỗ trợ.")

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
    
    await message.answer("✅ Yêu cầu đã được gửi tới Admin!")

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
    new_builder = InlineKeyboardBuilder().row(InlineKeyboardButton(text="✅ Hoàn thành", callback_data=f"done_{user_id}"))
    
    text = (callback.message.text or callback.message.caption) + f"\n\n📌 **Người nhận:** {admin_name}"
    if callback.message.text:
        await callback.message.edit_text(text, reply_markup=new_builder.as_markup())
    else:
        await callback.message.edit_caption(caption=text, reply_markup=new_builder.as_markup())

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
    await message.answer(get_daily_report())

# --- 6. VẬN HÀNH ---
def run_web():
    app.run(host='0.0.0.0', port=8080)

async def daily_scheduler():
    while True:
        now = datetime.now().strftime("%H:%M")
        if now == "13:00": # 20:00 VN
            await bot.send_message(ADMIN_GROUP_ID, f"🔔 **BÁO CÁO TỰ ĐỘNG**\n\n{get_daily_report()}")
            await asyncio.sleep(61)
        await asyncio.sleep(30)

async def main():
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.create_task(daily_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
        await bot.send_photo(ADMIN_GROUP_ID, photo=message.photo[-1].file_id, caption=header, reply_markup=builder.as_markup())
    
    await message.answer("✅ Đã gửi yêu cầu!")

# Xử lý nút "Nhận ticket"
@dp.callback_query(F.data.startswith("accept_"))
async def process_accept(callback: types.CallbackQuery):
    # 1. Lấy thông tin
    user_id = int(callback.data.split("_")[1])
    admin_name = callback.from_user.full_name  # Lấy tên của Admin vừa ấn nút
    
    # 2. Cập nhật Database (Ghi đè tên Admin vào cột handler_name)
    conn = sqlite3.connect('helpdesk.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tickets SET status = ?, handler_name = ? WHERE user_id = ? AND status = ?", 
        ("Đang xử lý", admin_name, user_id, "Mới")
    )
    conn.commit()
    conn.close()

    # 3. Thông báo cho khách hàng biết AI đang giúp họ
    await bot.send_message(user_id, f"👨‍💻 Chào bạn, {admin_name} đã nhận yêu cầu và đang xử lý cho bạn!")
    
    # 4. Tạo nút "Hoàn thành" mới
    new_builder = InlineKeyboardBuilder()
    new_builder.row(InlineKeyboardButton(text="✅ Hoàn thành", callback_data=f"done_{user_id}"))
    
    # 5. Cập nhật tin nhắn trong nhóm Admin để ai cũng thấy người đã nhận
    current_text = callback.message.text or callback.message.caption
    updated_text = f"{current_text}\n\n📌 **Đã nhận bởi:** {admin_name}"
    
    try:
        if callback.message.text:
            await callback.message.edit_text(updated_text, reply_markup=new_builder.as_markup())
        else:
            await callback.message.edit_caption(caption=updated_text, reply_markup=new_builder.as_markup())
    except Exception as e:
        print(f"Lỗi khi cập nhật giao diện: {e}")
    
    # Hiện thông báo nhỏ trên màn hình Admin
    await callback.answer(f"Bạn đã nhận ticket của khách!")

# Xử lý nút "Hoàn thành"
@dp.callback_query(F.data.startswith("done_"))
async def process_done(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    conn = sqlite3.connect('helpdesk.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = ? WHERE user_id = ?", ("Hoàn thành", user_id))
    conn.commit()
    conn.close()

    await bot.send_message(user_id, "✨ Yêu cầu của bạn đã hoàn thành!")
    
    try:
        await callback.message.edit_text(f"{callback.message.text}\n🏁 **TRẠNG THÁI:** ĐÃ XỬ LÝ", reply_markup=None)
    except:
        await callback.message.edit_caption(caption=f"{callback.message.caption}\n🏁 **TRẠNG THÁI:** ĐÃ XỬ LÝ", reply_markup=None)
    
    await callback.answer("Đã đóng ticket!")

# --- VỊ TRÍ 4: HÀM BÁO CÁO (Đặt trên hàm main) ---

def get_daily_report():
    try:
        conn = sqlite3.connect('helpdesk.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Mới'")
        new_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Đang xử lý'")
        pending_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Hoàn thành'")
        done_count = cursor.fetchone()[0]
        
        conn.close()
        
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        return (f"📊 **BÁO CÁO HỆ THỐNG**\n"
                f"⏰ Cập nhật: {now}\n\n"
                f"🆕 Mới: {new_count}\n"
                f"⏳ Đang xử lý: {pending_count}\n"
                f"✅ Hoàn thành: {done_count}")
    except Exception as e:
        return f"❌ Lỗi khi đọc Database: {e}"

# Handler xử lý lệnh /report
@dp.message(Command("report"))
async def send_report(message: Message):
    # Chỉ cho phép trong nhóm Admin hoặc bạn nhắn tin riêng cho Bot
    report_text = get_daily_report()
    await message.answer(report_text)

# --- PHẦN CHẠY WEB VÀ BOT (Luôn để ở cuối cùng) ---
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

async def daily_scheduler():
    """Hàm tự động gửi báo cáo lúc 20:00 (Giờ VN = 13:00 UTC)"""
    while True:
        now = datetime.now().strftime("%H:%M")
        # Render dùng giờ UTC, nên 13:00 UTC là 20:00 VN
        if now == "13:00": 
            report_text = get_daily_report()
            await bot.send_message(ADMIN_GROUP_ID, f"🔔 **BÁO CÁO TỰ ĐỘNG**\n\n{report_text}")
            await asyncio.sleep(61) 
        await asyncio.sleep(30)

async def main():
    # 1. Chạy Web giả cho Render
    threading.Thread(target=run_web, daemon=True).start()
    
    # 2. Chạy bộ hẹn giờ báo cáo tự động
    asyncio.create_task(daily_scheduler())
    
    print("Bot đang chạy, đã mở cổng giả và hẹn giờ báo cáo 20:00...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot đã dừng!")