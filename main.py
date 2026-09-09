import asyncio
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import httpx
from twscrape import API, gather

# ====== 配置区域（以后可以改） ======
ACCOUNTS = [          # 想抓取的账号（去掉@）
    "elonmusk",
    "OpenAI",
    "sama",
    "karpathy",
    "ylecun",
    "AndrewYNg",
    "hardmaru",
    "DrJimFan",
    "ronneyluo",
    "AIStockSavvy",
    # 后面可以继续加，先用这些测试
]

MAX_TWEETS_PER_USER = 5          # 每个账号抓最近几条
TOP_N = 10                       # 最终选几条
# =====================================

async def fetch_tweets():
    api = API()
    cookies = os.environ.get("X_COOKIES", "")
    if not cookies:
        raise Exception("没有找到 X_COOKIES，请检查 Secrets")

    await api.pool.add_account_cookies("scraper", cookies)
    
    all_tweets = []
    for username in ACCOUNTS:
        try:
            user = await api.user_by_login(username)
            tweets = await gather(api.user_tweets(user.id, limit=MAX_TWEETS_PER_USER))
            for t in tweets:
                all_tweets.append({
                    "user": username,
                    "text": t.rawContent,
                    "url": f"https://x.com/{username}/status/{t.id}",
                    "date": str(t.date),
                    "likes": t.likeCount or 0
                })
            print(f"已抓取 @{username}: {len(tweets)} 条")
        except Exception as e:
            print(f"抓取 @{username} 失败: {e}")
    
    return all_tweets

def summarize_with_groq(tweets):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "没有 GROQ_API_KEY，跳过 AI 总结"

    prompt = f"""你是一位专业的 AI 与股票投资分析师。
请从下面这些推文中，挑选出对「AI 技术和股票投资」最有价值的 {TOP_N} 条。
要求：
1. 输出中英对照
2. 每条写清楚为什么有价值
3. 按重要性排序

推文列表：
{json.dumps(tweets, ensure_ascii=False, indent=2)}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

async def main():
    print("开始抓取...")
    tweets = await fetch_tweets()
    print(f"共抓到 {len(tweets)} 条推文")

    summary = summarize_with_groq(tweets)

    # 生成网页
    Path("docs").mkdir(exist_ok=True)
    beijing = datetime.now(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日 %H:%M")
    
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>每日 AI 博主资讯</title>
<style>
body {{ font-family: system-ui; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
h1 {{ color: #1a1a1a; }}
pre {{ background: #f5f5f5; padding: 20px; border-radius: 8px; white-space: pre-wrap; }}
.time {{ color: #666; }}
</style>
</head>
<body>
<h1>每日十大博主资讯（AI + 股票）</h1>
<p class="time">更新时间（北京）：{beijing}</p>
<pre>{summary}</pre>
</body>
</html>
"""
    Path("docs/index.html").write_text(html, encoding="utf-8")
    print("网页已生成：docs/index.html")

if __name__ == "__main__":
    asyncio.run(main())
