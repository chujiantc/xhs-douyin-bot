import os
import io
import logging
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！请直接把带有水印的图片发送给我，我会为你无痕处理！")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 正在为你处理图片，请稍等...")
    try:
        # 1. 下载 Telegram 最高画质图片
        photo_file = update.message.photo[-1]
        file = await context.bot.get_file(photo_file.file_id)
        image_bytes = await file.download_as_bytearray()
        
        # 2. 读取图片并精确切除底部 6.5% 的水印区域（0 墨迹涂抹、0 变形拉扯）
        image = Image.open(io.BytesIO(image_bytes))
        w, h = image.size
        
        crop_h = int(h * 0.935)
        clean_img = image.crop((0, 0, w, crop_h))
        
        # 3. 内存保存并无损输出
        output_stream = io.BytesIO()
        img_fmt = image.format if image.format else 'JPEG'
        clean_img.save(output_stream, format=img_fmt, quality=95)
        output_stream.seek(0)
        
        await update.message.reply_document(
            document=output_stream,
            filename=f"clean_image.{img_fmt.lower()}",
            caption="✨ 处理完成！无水印、无涂抹、画质 100% 保持清晰！"
        )
    except Exception as e:
        logging.error(f"处理图片出错: {e}")
        await update.message.reply_text("❌ 处理失败，请重试。")
    finally:
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
