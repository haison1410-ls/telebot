import logging
import asyncio
import sqlite3  # <--- VỊ TRÍ 1: Import thư viện database ở đầu file
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
# --- CẤU HÌNH ---
API_TOKEN = '8576826985:AAE3CkWqTN0q7FuqXpZsOQkfenRObAFNBK4'
ADMIN_GROUP_ID = -5260948214 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- VỊ TRÍ 2: HÀM KHỞI TẠO DATABASE (Đặt ngay dưới phần cấu hình) ---
def init_db():
    conn = sqlite3.connect('helpdesk.db')
    cursor = conn.cursor()
    # Tạo bảng lưu ticket nếu chưa có
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            user_id INTEGER,
            issue TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db() # Chạy luôn để tạo file helpdesk.db ngay khi bật bot

# --- VỊ TRÍ 3: CÁC HÀM XỬ LÝ (Handlers) ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Chào mừng bạn! Gửi yêu cầu hỗ trợ tại đây.")

@dp.message(F.chat.type == "private")
async def handle_user_request(message: Message):
    user_id = message.from_user.id
    content = message.text or "[Hình ảnh]"

    # LƯU VÀO DATABASE
    conn = sqlite3.connect('helpdesk.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tickets (user_id, issue, status) VALUES (?, ?, ?)", 
                   (user_id, content, "Mới"))
    conn.commit()
    conn.close()

    # Gửi nút bấm cho Admin
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🙋‍♂️ Nhận ticket", callback_data=f"accept_{user_id}"))
    
    header = f"📩 **TICKET MỚI**\n👤: {message.from_user.full_name}\n🆔 ID: `{user_id}`"
    if message.text:
        await bot.send_message(ADMIN_GROUP_ID, f"{header}\n📝: {message.text}", reply_markup=builder.as_markup())
    elif message.photo:
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