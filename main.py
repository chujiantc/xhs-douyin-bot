import os
import io
import logging
import cv2
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def remove_watermark_hsv(image_bytes):
    """
    通过 HSV 色彩空间精准抓取白色水印，
    强制排除黑色轮廓线与彩色衣服，彻底杜绝黑色墨迹涂抹变形。
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # 1. 锁定右下角区域 (高度 72%~100%，宽度 65%~100%)
    y1, y2 = int(h * 0.72), h
    x1, x2 = int(w * 0.65), w
    roi = img[y1:y2, x1:x2]

    # 2. 转 HSV 色彩空间
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # 3. 提取白色/浅灰色水印 (低饱和度 S < 50，高亮度 V > 180)
    white_mask = cv2.inRange(hsv_roi, np.array([0, 0, 180]), np.array([180, 50, 255]))

    # 4. 提取黑色轮廓线与暗色区域 (V < 90)，这些区域必须绝对保护！
    dark_mask = cv2.inRange(hsv_roi, np.array([0, 0, 0]), np.array([180, 255, 90]))

    # 5. 提取高饱和度色彩 (S > 60，如红衣服、嘴巴等)，这些区域也必须保护！
    color_mask = cv2.inRange(hsv_roi, np.array([0, 60, 0]), np.array([180, 255, 255]))

    # 6. 最终蒙版 = 白色区域 MINUS 黑色线条 MINUS 鲜艳色彩
    final_roi_mask = cv2.bitwise_and(white_mask, cv2.bitwise_not(dark_mask))
    final_roi_mask = cv2.bitwise_and(final_roi_mask, cv2.bitwise_not(color_mask))

    # 7. 微膨胀 1 像素，仅覆盖水印字体边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated_mask = cv2.dilate(final_roi_mask, kernel, iterations=1)

    # 8. 映射回全图蒙版
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = dilated_mask

    # 9. 使用 Navier-Stokes 算法微缝平滑，半径仅为 2
    inpainted = cv2.inpaint(img, full_mask, inpaintRadius=2, flags=cv2.INPAINT_NS)

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
        
        clean_bytes = remove_watermark_hsv(image_bytes)
        
        await update.message.reply_document(
            document=io.BytesIO(clean_bytes),
            filename="clean_image.jpg",
            caption="✨ 已为你无痕消除小红书水印！"
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
