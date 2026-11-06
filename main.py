import os
import re
import logging
import requests
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 设置日志记录
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！请将小红书或抖音的分享链接发送给我，我会为你提取无水印高清原图！")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = re.findall(r'https?://[^\s]+', text)
    
    if not urls:
        await update.message.reply_text("❌ 未检测到有效链接，请发送正确的分享链接。")
        return
    
    target_url = urls[0]
    msg = await update.message.reply_text("⏳ 正在为你提取无水印高清图片，请稍等...")
    
    try:
        # 调用无水印解析接口
        api_url = f"https://api.pearktrue.cn/api/all/parse.php?url={target_url}"
        response = requests.get(api_url, timeout=15).json()
        
        images = []
        if response.get("code") == 200 and "data" in response:
            data = response["data"]
            images = data.get("images") or data.get("pics") or []
            
        if images:
            # Telegram 规定一次最多批量发送 10 张图片
            chunk_size = 10
            for i in range(0, len(images), chunk_size):
                media_group = [InputMediaPhoto(media=img_url) for img_url in images[i:i+chunk_size]]
                await update.message.reply_media_group(media=media_group)
            await msg.delete()
        else:
            await msg.edit_text("⚠️ 未能提取到高清图片，请确认链接是否为图文帖子。")
    except Exception as e:
        logging.error(f"解析出错: {e}")
        await msg.edit_text("❌ 解析请求失败，请稍后再试。")

if __name__ == '__main__':
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("未设置 BOT_TOKEN 环境变量！")
    
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🤖 Bot 已成功启动！")
    app.run_polling()
