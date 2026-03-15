"""
TradeVed Pipeline Logic
All 3 agents + LLM analysis + content generation
"""
import yt_dlp, time, os, requests
import pandas as pd
from pytrends.request import TrendReq

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
SEARCH_QUERIES = {
    "indices":   ["nifty 50 trading strategy 2026",     "banknifty options trading today"],
    "options":   ["option buying strategy nifty india", "options trading beginners india"],
    "algo":      ["algo trading india tutorial",        "backtesting trading strategy india"],
    "education": ["stock market basics hindi 2026",     "trading for beginners india"],
    "technical": ["technical analysis nifty rsi ema",   "candlestick patterns trading india"],
    "investing": ["share market india long term",       "mutual funds vs stocks india"],
}

FINANCE_KEYWORDS = [
    "nifty","banknifty","sensex","stock","trading","market","option","future",
    "invest","equity","algo","rsi","ema","candlestick","breakout","support",
    "resistance","backtest","profit","trade","chart","technical","fundamental",
    "portfolio","sebi","rbi","ipo","mutual fund","bullish","bearish",
]

TREND_KEYWORDS = [
    "nifty 50 today","option trading strategy",
    "stock market crash","algo trading india","best stocks to buy",
]

MIN_VIEWS        = 10000
RESULTS_PER_QUERY = 5
MAX_TRANSCRIBE   = 3
NUM_IDEAS        = 3


# ─────────────────────────────────────────
# AGENT 1 — Viral Finance Video Finder
# ─────────────────────────────────────────
def run_agent1():
    print("🔍 Agent 1: Finding viral finance videos...")
    all_videos = []
    ydl_opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True, "playlistend": RESULTS_PER_QUERY,
    }

    for category, queries in SEARCH_QUERIES.items():
        for query in queries:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    results = ydl.extract_info(f"ytsearch{RESULTS_PER_QUERY}:{query}", download=False)
                    if not results or "entries" not in results:
                        continue
                    for video in results["entries"]:
                        if not video:
                            continue
                        views = video.get("view_count", 0) or 0
                        likes = video.get("like_count", 0) or 0
                        title = video.get("title", "")
                        desc  = str(video.get("description", ""))[:400]
                        if views < MIN_VIEWS:
                            continue
                        combined = f"{title} {desc}".lower()
                        if not any(kw in combined for kw in FINANCE_KEYWORDS):
                            continue
                        video_url = f"https://youtube.com/watch?v={video.get('id','')}"
                        all_videos.append({
                            "category":        category,
                            "hashtag":         query,
                            "title":           title,
                            "likes":           likes,
                            "views":           views,
                            "caption":         desc,
                            "video_url":       video_url,
                            "url":             video_url,
                            "owner":           video.get("channel", ""),
                            "engagement_rate": round(likes / max(views, 1) * 100, 3),
                            "thumbnail":       video.get("thumbnail", ""),
                            "duration_secs":   video.get("duration", 0),
                        })
            except Exception as e:
                print(f"  ⚠️ {query}: {e}")
                continue

    all_videos.sort(key=lambda x: x["views"], reverse=True)
    print(f"✅ Agent 1 Done — {len(all_videos)} videos found")
    return all_videos


# ─────────────────────────────────────────
# AGENT 2 — Trending Topics (Google Trends)
# ─────────────────────────────────────────
def run_agent2():
    print("📈 Agent 2: Fetching Google Trends...")
    pytrends    = TrendReq(hl="en-IN", tz=330)
    all_trends  = {}
    all_rising  = []
    all_realtime = []

    groups = [
        ["nifty 50 today","banknifty","option trading","stock market india","sensex today"],
        ["algo trading","technical analysis","candlestick","rsi indicator","backtest"],
    ]
    for group in groups:
        try:
            pytrends.build_payload(group, timeframe="now 7-d", geo="IN")
            df = pytrends.interest_over_time()
            if not df.empty:
                for kw in group:
                    if kw in df.columns:
                        all_trends[kw] = int(df[kw].mean())
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️ trends group: {e}")

    all_trends = dict(sorted(all_trends.items(), key=lambda x: x[1], reverse=True))

    for topic in ["nifty 50", "option trading", "stock market"]:
        try:
            pytrends.build_payload([topic], timeframe="now 7-d", geo="IN")
            related   = pytrends.related_queries()
            rising_df = related.get(topic, {}).get("rising")
            if rising_df is not None and not rising_df.empty:
                all_rising.extend(rising_df["query"].head(3).tolist())
            time.sleep(1)
        except:
            pass

    finance_words = ["stock","nifty","sensex","market","sebi","rbi","trading","share","invest","budget","ipo"]
    try:
        rt = pytrends.realtime_trending_searches(pn="IN")
        for _, row in rt.iterrows():
            if any(w in str(row.get("title","")).lower() for w in finance_words):
                all_realtime.append(row.get("title",""))
    except:
        pass

    print(f"✅ Agent 2 Done — {len(all_trends)} topics, {len(all_rising)} rising")
    return all_trends, all_rising, all_realtime


# ─────────────────────────────────────────
# AGENT 3 — Transcribe (Whisper)
# ─────────────────────────────────────────
def run_agent3(viral_reels):
    print("🎙️ Agent 3: Transcribing top videos...")
    try:
        import whisper
        whisper_model = whisper.load_model("base")
    except Exception as e:
        print(f"  ⚠️ Whisper not available: {e} — using descriptions")
        return [{**r, "transcript": r.get("caption", "")} for r in viral_reels[:MAX_TRANSCRIBE]]

    top_reels         = sorted(viral_reels, key=lambda x: x["views"], reverse=True)[:MAX_TRANSCRIBE]
    transcribed_reels = []

    for i, reel in enumerate(top_reels):
        audio_path = f"/tmp/tv_{i}.mp3"
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"/tmp/tv_{i}",
                "postprocessors": [{"key": "FFmpegExtractAudio","preferredcodec": "mp3","preferredquality": "96"}],
                "quiet": True, "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([reel["video_url"]])

            if os.path.exists(audio_path):
                result     = whisper_model.transcribe(audio_path, language="en")
                transcript = result["text"].strip()
                transcribed_reels.append({**reel, "transcript": transcript})
                os.remove(audio_path)
            else:
                raise FileNotFoundError("audio not created")
        except Exception as e:
            print(f"  ⚠️ reel {i}: {e} — using description")
            transcribed_reels.append({**reel, "transcript": reel.get("caption", "")})

    print(f"✅ Agent 3 Done — {len(transcribed_reels)} transcribed")
    return transcribed_reels


# ─────────────────────────────────────────
# LLM HELPERS
# ─────────────────────────────────────────
def call_llm(prompt, provider, gemini_key, ollama_model):
    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        model    = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        return response.text

    elif provider == "ollama":
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=300
        )
        return response.json().get("response", "")

    raise ValueError(f"Unknown provider: {provider}")


# ─────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────
def run_analysis(transcribed_reels, trending, rising, realtime, provider, gemini_key, ollama_model):
    print(f"🧠 Analysis via {provider}...")
    reels_text = ""
    for i, r in enumerate(transcribed_reels):
        reels_text += f"""
VIDEO {i+1}:
  Category   : {r.get('category','').upper()}
  Title      : {r.get('title','N/A')}
  Channel    : {r.get('owner','')}
  Performance: {r.get('views',0):,} views · {r.get('likes',0):,} likes
  Description: {r.get('caption','')[:200]}
  Transcript : {r.get('transcript','')[:500]}
---"""

    trends_str   = "\n".join([f"  {k}: {v}/100" for k, v in trending.items()])
    rising_str   = ", ".join(rising[:6])   if rising   else "none"
    realtime_str = ", ".join(realtime[:4]) if realtime else "none"

    prompt = f"""You are Head of Content Strategy at TradeVed — India's systematic trading education platform.
Audience: Retail traders 20-35 yrs learning options, algo trading, backtesting, technical analysis.
Tone: Educational, empowering, professional. Never hype or get-rich-quick.

=== VIRAL FINANCE VIDEOS THIS WEEK ===
{reels_text}

=== GOOGLE TRENDS INDIA (Last 7 Days) ===
Weekly Interest:
{trends_str}
Rising queries : {rising_str}
Real-time buzz : {realtime_str}

=== YOUR ANALYSIS ===

## WHY THIS FINANCE CONTENT WENT VIRAL
What hooks, emotions, formats and trading topics drove engagement?

## TOP 3 TRENDING TRADING TOPICS IN INDIA THIS WEEK
Which topics are hot and perfect for TradeVed right now?

## CONTENT FORMAT WINNING RIGHT NOW
What style is performing best?

## TOP 3 CONTENT OPPORTUNITIES FOR TRADEVED
Specific opportunities this week.

## WHAT TO AVOID
What doesn't fit TradeVed's educational brand?"""

    result = call_llm(prompt, provider, gemini_key, ollama_model)
    print(f"✅ Analysis done — {len(result)} chars")
    return result


# ─────────────────────────────────────────
# CONTENT GENERATION
# ─────────────────────────────────────────
def run_content_gen(analysis, provider, gemini_key, ollama_model):
    print(f"📝 Content generation via {provider}...")

    prompt = f"""You are TradeVed's Instagram content creator.
TradeVed = India's best systematic trading education platform.
Audience = Retail traders in India, 20-35 yrs, learning options, algo, backtesting, technical analysis.
Tone = Educational, empowering. Make complex trading simple. Never hype.
Always end with: follow TradeVed to learn systematic trading.

=== INTELLIGENCE FROM AI AGENTS ===
{analysis}

=== YOUR TASK ===
Create exactly {NUM_IDEAS} Instagram Reel ideas for TradeVed. Each must cover a specific trading topic.

For EACH idea use this EXACT format:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDEA [N]: [TITLE]
Topic: [specific trading topic]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS WILL GO VIRAL:
[what viral pattern + why traders will share it]

HOOK (First 3 seconds):
[exact words — must make traders stop scrolling]

FULL REEL SCRIPT (30-45 seconds):
[00:00-00:03] HOOK    : [text]
[00:03-00:08] SETUP   : [text]
[00:08-00:20] CONTENT : [text with real trading examples/numbers]
[00:20-00:35] PAYOFF  : [key insight traders can use immediately]
[00:35-00:45] CTA     : [follow TradeVed]

ON-SCREEN TEXT OVERLAYS:
[text to flash on screen at each section]

CAPTION (max 120 words):
[conversational, educational, ends with a question, mentions TradeVed]

HASHTAGS (25 tags):
[5 huge + 10 mid trading + 10 niche Indian trading]

BEST TIME TO POST:
[day + time + reason for Indian traders]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    result = call_llm(prompt, provider, gemini_key, ollama_model)
    print(f"✅ Content done — {len(result)} chars")
    return result
