import os
import re
import json
import logging
import requests
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 设置日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

def get_real_url(url):
    """还原小红书/抖音短链接"""
    try:
        res = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=10)
        return res.url
    except Exception:
        return url

def extract_xhs_native(url):
    """直连小红书提取最高清无水印原图"""
    try:
        real_url = get_real_url(url)
        res = requests.get(real_url, headers=HEADERS, timeout=10)
        html = res.text
        
        # 提取页面 window.__INITIAL_STATE__ 内置数据
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});</script>', html, re.DOTALL)
        if match:
            try:
                state = json.loads(match.group(1))
                note_data = None
                if "note" in state and "noteDetailMap" in state["note"]:
                    detail_map = state["note"]["noteDetailMap"]
                    for k, v in detail_map.items():
                        if "note" in v:
                            note_data = v["note"]
                            break
                if note_data and "imageList" in note_data:
                    images = []
                    for img in note_data["imageList"]:
                        trace = img.get("traceId")
                        if trace:
                            images.append(f"https://sns-img-bd.xhscdn.com/{trace}")
                        else:
                            url_default = img.get("urlDefault") or img.get("urlPre")
                            if url_default:
                                images.append(url_default.split('?')[0])
                    if images:
                        return images
            except Exception:
                pass

        # 备用正则表达式捕获图片ID
        trace_ids = re.findall(r'"(?:urlTraceId|traceId)":"([a-zA-Z0-9\-_]+)"', html)
        if trace_ids:
            valid_ids = [t for t in dict.fromkeys(trace_ids) if len(t) >= 20]
            if valid_ids:
                return [f"https://sns-img-bd.xhscdn.com/{tid}" for tid in valid_ids]

    except Exception as e:
        logging.warning(f"直连解析异常: {e}")
    return []

def parse_all_sources(target_url):
    """全自动多路解析总控"""
    # 1. 小红书优先直连解析
    if "xhslink" in target_url or "xiaohongshu" in target_url:
        imgs = extract_xhs_native(target_url)
        if imgs:
            return imgs
            
    # 2. 备用 API 接口池（支持小红书与抖音）
    real_url = get_real_url(target_url)
    api_endpoints = [
        f"https://api.vvhan.com/api/hy/video?url={real_url}",
        f"https://tenapi.cn/v2/images?url={real_url}",
        f"https://api.pearktrue.cn/api/all/parse.php?url={real_url}"
    ]
    
    for api in api_endpoints:
        try:
            r = requests.get(api, headers=HEADERS, timeout=8).json()
            if isinstance(r, dict):
                data = r.get("data")
                if isinstance(data, dict):
                    imgs = data.get("images") or data.get("pics") or data.get("cover")
                    if isinstance(imgs, list) and len(imgs) > 0:
                        return imgs
                    elif isinstance(imgs, str):
                        return [imgs]
                elif isinstance(r.get("images"), list):
                    return r["images"]
                elif isinstance(r.get("url"), list):
                    return r["url"]
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
        images = parse_all_sources(target_url)
        if images:
            unique_imgs = list(dict.fromkeys(images))
            chunk_size = 10
            for i in range(0, len(unique_imgs), chunk_size):
                media_group = [InputMediaPhoto(media=img_url) for img_url in unique_imgs[i:i+chunk_size]]
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
