import os
import io
import logging
import cv2
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def remove_watermark_inpaint(image_bytes):
    """使用 OpenCV 智能修复算法彻底抹去右下角账号名与小红书图标水印"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # 扩大蒙版范围：覆盖右下角 85%~100% 垂直高度与 70%~100% 水平宽度
    mask = np.zeros((h, w), dtype=np.uint8)
    y1, y2 = int(h * 0.85), h
    x1, x2 = int(w * 0.70), w
    mask[y1:y2, x1:x2] = 255

    # 智能像素融合填补
    inpainted = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

    _, buffer = cv2.imencode(".jpg", inpainted, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return buffer.tobytes()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！请直接把带有水印的图片发送给我，我会为你智能抹去水印！")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 正在进行智能图像修复，抹去水印中...")
    try:
        photo_file = update.message.photo[-1]
        file = await context.bot.get_file(photo_file.file_id)
        image_bytes = await file.download_as_bytearray()
        
        clean_bytes = remove_watermark_inpaint(image_bytes)
        
        await update.message.reply_document(
            document=io.BytesIO(clean_bytes),
            filename="inpaint_clean.jpg",
            caption="✨ 已为你彻底抹去小红书图标与水印！"
        )
    except Exception as e:
        logging.error(f"处理图片出错: {e}")
        await update.message.reply_text(f"❌ 处理失败: {e}")
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
