import os
import io
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！请直接把图片发送给我！")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 收到图片，正在为你处理...")
    try:
        # 1. 获取最高画质图片
        photo_file = update.message.photo[-1]
        
        # 2. 从 Telegram 服务器下载图片数据
        file = await context.bot.get_file(photo_file.file_id)
        image_bytes = await file.download_as_bytearray()
        
        # 3. 将图片包装为无损文件发回
        await update.message.reply_document(
            document=io.BytesIO(image_bytes),
            filename="image_original.jpg",
            caption="✨ 已为你提取无损高清原图文件！"
        )
    except Exception as e:
        logging.error(f"处理图片出错: {e}")
        await update.message.reply_text(f"❌ 处理失败: {e}")
    finally:
        # 无论成功或失败，都及时删除“正在处理”提示
        try:
            await msg.delete()
        except Exception:
            pass

if __name__ == '__main__':
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("未设置 BOT_TOKEN 环境变量！")
    
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("🤖 Bot 已成功启动！")
    app.run_polling()
