import os
import io
import logging
import cv2
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def remove_watermark_precise(image_bytes):
    """精准识别小红书白色水印字符与 Logo，只修复文字笔画，绝不拖拉画面"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # 1. 扩大覆盖高度到 72%~100%，确保完全吃进上方的 (小红书) 椭圆图标
    y1, y2 = int(h * 0.72), h
    x1, x2 = int(w * 0.65), w
    roi = img[y1:y2, x1:x2]

    # 2. 转灰度图并提取白色/高亮的水印字符（小红书 Logo 与账号字体均为白色）
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary_mask = cv2.threshold(gray_roi, 175, 255, cv2.THRESH_BINARY)

    # 3. 对水印笔画外扩 2 个像素，完美覆盖半透明边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated_mask = cv2.dilate(binary_mask, kernel, iterations=2)

    # 4. 生成全图精准笔画蒙版
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = dilated_mask

    # 5. 仅对字符微小线条做补色（半径仅为 3，绝无模糊变形）
    inpainted = cv2.inpaint(img, full_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

    _, buffer = cv2.imencode(".jpg", inpainted, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return buffer.tobytes()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！请直接把带有水印的图片发送给我，我会为你精准消除水印！")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 正在进行精准水印消除，请稍等...")
    try:
        photo_file = update.message.photo[-1]
        file = await context.bot.get_file(photo_file.file_id)
        image_bytes = await file.download_as_bytearray()
        
        clean_bytes = remove_watermark_precise(image_bytes)
        
        await update.message.reply_document(
            document=io.BytesIO(clean_bytes),
            filename="clean_image.jpg",
            caption="✨ 已为你精准抹除小红书图标与账号水印！"
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
