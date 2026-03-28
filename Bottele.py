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
    user_id = int(callback.data.split("_")[1])
    
    # CẬP NHẬT TRẠNG THÁI TRONG DATABASE
    conn = sqlite3.connect('helpdesk.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = ? WHERE user_id = ? AND status = ?", ("Đang xử lý", user_id, "Mới"))
    conn.commit()
    conn.close()

    await bot.send_message(user_id, f"👨‍💻 {callback.from_user.full_name} đang xử lý yêu cầu của bạn!")
    
    new_builder = InlineKeyboardBuilder()
    new_builder.row(InlineKeyboardButton(text="✅ Hoàn thành", callback_data=f"done_{user_id}"))
    
    # Sửa tin nhắn trong nhóm Admin (Dùng try-except để tránh lỗi nếu tin nhắn quá cũ)
    try:
        await callback.message.edit_text(f"{callback.message.text}\n\n📌 **Đang xử lý bởi:** {callback.from_user.full_name}", reply_markup=new_builder.as_markup())
    except:
        await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n📌 **Đang xử lý bởi:** {callback.from_user.full_name}", reply_markup=new_builder.as_markup())
    
    await callback.answer("Đã nhận ticket!")

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

# --- VỊ TRÍ 4: HÀM CHẠY CHÍNH (Cuối file) ---
from flask import Flask
import threading

# 1. Tạo một ứng dụng Web siêu nhỏ
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    # Render yêu cầu mở cổng 8080 để kiểm tra tình trạng sống/chết
    app.run(host='0.0.0.0', port=8080)

# 2. Sửa lại hàm chạy chính để chạy cả Web và Bot
async def main():
    # Chạy Web Server giả trong một luồng riêng (luồng daemon để tự tắt khi bot tắt)
    threading.Thread(target=run_web, daemon=True).start()
    
    print("Bot đang chạy và đã mở cổng giả 8080 cho Render...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Cấu hình nhật ký để theo dõi lỗi
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot đã dừng!")
def get_daily_report():
    conn = sqlite3.connect('helpdesk.db')
    cursor = conn.cursor()
    
    # Đếm các trạng thái
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Mới'")
    new = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Đang xử lý'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Hoàn thành'")
    done = cursor.fetchone()[0]
    
    conn.close()
    
    now = datetime.now().strftime("%d/%m/%Y")
    report = (f"📊 **BÁO CÁO TỔNG KẾT NGÀY {now}**\n\n"
              f"🆕 Ticket mới: {new}\n"
              f"⏳ Đang xử lý: {pending}\n"
              f"✅ Đã hoàn thành: {done}\n"
              f"----------------------------\n"
              f"🔥 Chúc đội ngũ kỹ thuật nghỉ ngơi vui vẻ!")
    return report

# Lệnh để Admin chủ động xem báo cáo bất cứ lúc nào
@dp.message(Command("report"), F.chat.id == ADMIN_GROUP_ID)
async def send_report(message: Message):
    report_text = get_daily_report()
    await message.answer(report_text)