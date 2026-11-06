import os
import re
import logging
import json
import requests
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9'
}

def extract_xhs_native(url):
    """直接解析小红书页面获取原图数组"""
    try:
        session = requests.Session()
        res = session.get(url, headers=HEADERS, allow_redirects=True, timeout=10)
        html = res.text
        
        # 从小红书网页页面内置 JSON 提取原图 URL
        img_urls = re.findall(r'"urlTraceId":"([^"]+)"', html)
        if img_urls:
            # 拼接高清无水印图片链接
            images = [f"https://sns-img-bd.xhscdn.com/{trace_id}" for trace_id in dict.fromkeys(img_urls)]
            return images
            
        # 备用方案：正则直接匹配原始图片域名
        raw_imgs = re.findall(r'https://sns-img-[^"\s\\]+?\.xhscdn\.com/[0-9a-zA-Z\-_]+', html)
        if raw_imgs:
            clean_imgs = list(dict.fromkeys([img.split('?')[0] for img in raw_imgs if '! ' not in img]))
            return clean_imgs
    except Exception as e:
        logging.warning(f"小红书直连解析异常: {e}")
    return []

def parse_watermark_free(target_url):
    # 1. 优先采用直连小红书解析
    if "xhslink.com" in target_url or "xiaohongshu.com" in target_url:
        native_imgs = extract_xhs_native(target_url)
        if native_imgs:
            return native_imgs

    # 2. 通用 API 备用轮询
    api_list = [
        f"https://api.pearktrue.cn/api/all/parse.php?url={target_url}",
        f"https://tenapi.cn/v2/images?url={target_url}"
    ]
    
    for api in api_list:
        try:
            r = requests.get(api, headers=HEADERS, timeout=8).json()
            if "data" in r and isinstance(r["data"], dict):
                imgs = r["data"].get("images") or r["data"].get("pics")
                if isinstance(imgs, list) and len(imgs) > 0:
                    return imgs
        except Exception:
            continue
            
    return []

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
        logging.error(f"处理出错: {e}")
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
