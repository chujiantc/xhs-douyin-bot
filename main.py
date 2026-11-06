import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 设置日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！请直接把图片发送给我！")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 获取用户发送的最高清晰度图片 (photo[-1] 即最高画质版本)
    photo_file = update.message.photo[-1]
    
    msg = await update.message.reply_text("⏳ 收到图片，正在为你处理...")
    
    # 将图片以无损文件 (Document) 形式发回，避免 Telegram 压画质
    await update.message.reply_document(
        document=photo_file.file_id,
        caption="✨ 已为你提取最高清原图文件！"
    )
    await msg.delete()

if __name__ == '__main__':
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("未设置 BOT_TOKEN 环境变量！")
    
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    
    # 监听用户发送的图片消息 (PHOTO)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("🤖 Bot 已成功启动！")
    app.run_polling()
