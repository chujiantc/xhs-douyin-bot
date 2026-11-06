import os
import io
import logging
import cv2
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def remove_watermark_inpaint(image_bytes):
    """使用 OpenCV 智能修复算法抹去右下角水印，100% 保留图片尺寸与底部画面"""
    # 1. 字节流转 OpenCV 图像格式
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # 2. 精准定位小红书水印范围（右下角）
    mask = np.zeros((h, w), dtype=np.uint8)
    y1, y2 = int(h * 0.91), int(h * 0.99)   # 底部 91% ~ 99% 区域
    x1, x2 = int(w * 0.58), int(w * 0.98)   # 右侧 58% ~ 98% 区域
    mask[y1:y2, x1:x2] = 255

    # 3. 智能像素填补 (Telea 算法)，参考周边背景色自动擦除水印
    inpainted = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

    # 4. 转回 JPEG 字节流
    _, buffer = cv2.imencode(".jpg", inpainted, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return buffer.tobytes()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！请直接把带有水印的图片发送给我，我会为你智能抹去水印！")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 正在进行智能图像修复，抹去水印中...")
    try:
        # 下载图片
        photo_file = update.message.photo[-1]
        file = await context.bot.get_file(photo_file.file_id)
        image_bytes = await file.download_as_bytearray()
        
        # 智能抹除水印
        clean_bytes = remove_watermark_inpaint(image_bytes)
        
        # 发回无损文件
        await update.message.reply_document(
            document=io.BytesIO(clean_bytes),
            filename="inpaint_clean.jpg",
            caption="✨ 已为你智能抹去水印（完整保留画面尺寸与细节）！"
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
