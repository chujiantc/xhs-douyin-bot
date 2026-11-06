import os
import re
import logging
import requests
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
}

def parse_watermark_free(target_url):
    # 还原短链接
    try:
        res = requests.get(target_url, headers=HEADERS, allow_redirects=True, timeout=10)
        real_url = res.url
    except Exception:
        real_url = target_url

    # 接口池（主接口 + 备用接口），防止单一域名 DNS 故障
    api_list = [
        f"https://api.vvhan.com/api/hy/video?url={real_url}",
        f"https://tenapi.cn/v2/images?url={real_url}",
        f"https://api.pearktrue.cn/api/all/parse.php?url={real_url}"
    ]
    
    images = []
    for api in api_list:
        try:
            r = requests.get(api, headers=HEADERS, timeout=8).json()
            # 兼容解析不同接口返回的数据格式
            if "data" in r and isinstance(r["data"], dict):
                imgs = r["data"].get("images") or r["data"].get("pics") or r["data"].get("cover")
                if isinstance(imgs, list) and len(imgs) > 0:
                    images = imgs
                    break
                elif isinstance(imgs, str):
                    images = [imgs]
                    break
            elif "images" in r and isinstance(r["images"], list):
                images = r["images"]
                break
            elif "url" in r and isinstance(r["url"], list):
                images = r["url"]
                break
        except Exception as e:
            logging.warning(f"接口请求异常: {e}")
            continue
            
    return images

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
        images = parse_watermark_free(target_url)
        if images:
            chunk_size = 10
            for i in range(0, len(images), chunk_size):
                media_group = [InputMediaPhoto(media=img_url) for img_url in images[i:i+chunk_size]]
                await update.message.reply_media_group(media=media_group)
            await msg.delete()
        else:
            await msg.edit_text("⚠️ 未能提取到高清图片，请确认链接是否为图文帖子。")
    except Exception as e:
        logging.error(f"处理过程中出错: {e}")
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
