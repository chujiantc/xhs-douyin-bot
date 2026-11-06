import os
import io
import logging
import cv2
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def remove_watermark_tophat(image_bytes):
    """
    使用顶帽变换 (Top-Hat) 精准提取浅色/白色水印笔画，
    不误伤浅色背景与人物线条，彻底解决大面积涂抹变形问题。
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    # 1. 锁定右下角区域 (高度 70%~100%，宽度 65%~100%)
    y1, y2 = int(h * 0.70), h
    x1, x2 = int(w * 0.65), w
    roi = img[y1:y2, x1:x2]

    # 2. 转灰度图
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 3. 顶帽变换 (Top-Hat)：专门提取比背景亮的小结构（文字笔画、图标轮廓），忽略大片浅色背景
    kernel_tophat = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    tophat = cv2.morphologyEx(gray_roi, cv2.MORPH_TOPHAT, kernel_tophat)

    # 4. 对顶帽提取出的细节进行二值化，只保留高亮笔画
    _, binary_mask = cv2.threshold(tophat, 35, 255, cv2.THRESH_BINARY)

    # 5. 微弱膨胀蒙版，确保覆盖字符边缘羽化
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated_mask = cv2.dilate(binary_mask, kernel_dilate, iterations=1)

    # 6. 还原为全图蒙版
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = dilated_mask

    # 7. 仅对笔画线条做精准微缝修补 (inpaintRadius=2，绝不拉扯周围画质)
    inpainted = cv2.inpaint(img, full_mask, inpaintRadius=2, flags=cv2.INPAINT_TELEA)

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
        
        clean_bytes = remove_watermark_tophat(image_bytes)
        
        await update.message.reply_document(
            document=io.BytesIO(clean_bytes),
            filename="clean_image.jpg",
            caption="✨ 已为你精准无痕消除小红书水印！"
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
