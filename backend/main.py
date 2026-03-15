from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio, os, yt_dlp, whisper
from pytrends.request import TrendReq
import google.genai as genai
import requests

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.join(BASE_DIR, "frontend")
if os.path.exists(FRONTEND_PATH):
    app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    index = os.path.join(FRONTEND_PATH, "index.html")
    return FileResponse(index) if os.path.exists(index) else {"message": "TradeVed API running"}

state = {
    "status": "idle", "step": 0, "step_label": "", "error": "",
    "viral_reels": [], "trending": {}, "rising": [], "realtime": [],
    "transcribed": [], "analysis": "", "content": "",
    "llm_mode": "gemini", "gemini_key": "", "ollama_model": "llama3",
}

SEARCH_QUERIES = {
    "indices":   ["nifty 50 trading strategy 2024",      "banknifty options trading today"],
    "options":   ["option buying strategy nifty india",  "options trading beginners india"],
    "algo":      ["algo trading india tutorial",         "backtesting trading strategy india"],
    "education": ["stock market basics hindi 2024",      "trading for beginners india"],
    "technical": ["technical analysis nifty rsi ema",    "candlestick patterns trading india"],
    "investing": ["share market india long term",        "mutual funds vs stocks india"],
}
FINANCE_KW = [
    "nifty","banknifty","sensex","stock","trading","market","option","future","invest",
    "equity","algo","rsi","ema","candlestick","breakout","support","resistance","backtest",
    "profit","trade","chart","technical","portfolio","sebi","rbi","ipo","mutual fund","bullish","bearish"
]

def is_finance(text):
    return any(k in str(text).lower() for k in FINANCE_KW)

def setstep(n, label):
    state["step"] = n
    state["step_label"] = label
    state["status"] = "running"

def call_llm(prompt):
    """Single LLM caller — uses gemini or ollama based on state"""
    if state["llm_mode"] == "gemini":
        client = genai.Client(api_key=state["gemini_key"])
        return client.models.generate_content(model="gemini-2.0-flash", contents=prompt).text
    else:
        # Ollama runs locally on user's machine — called from backend
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": state["ollama_model"], "prompt": prompt, "stream": False},
            timeout=300
        )
        return r.json().get("response", "")

async def run_pipeline():
    try:
        state["status"] = "running"
        state["error"]  = ""

        # STEP 1
        setstep(1, "Agent 1: Finding viral finance videos on YouTube...")
        viral = []
        ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": 5}
        for category, queries in SEARCH_QUERIES.items():
            for query in queries:
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        res = ydl.extract_info(f"ytsearch5:{query}", download=False)
                        if not res or "entries" not in res: continue
                        for v in res["entries"]:
                            if not v: continue
                            views = v.get("view_count", 0) or 0
                            likes = v.get("like_count",  0) or 0
                            title = v.get("title", "")
                            desc  = str(v.get("description", ""))[:400]
                            if views < 10000: continue
                            if not is_finance(f"{title} {desc}"): continue
                            vid_url = f"https://youtube.com/watch?v={v.get('id','')}"
                            viral.append({
                                "category": category, "hashtag": query, "title": title,
                                "likes": likes, "views": views, "caption": desc,
                                "video_url": vid_url, "url": vid_url,
                                "owner": v.get("channel", ""),
                                "engagement_rate": round(likes / max(views, 1) * 100, 3),
                            })
                except: pass
                await asyncio.sleep(0.3)
        viral.sort(key=lambda x: x["views"], reverse=True)
        state["viral_reels"] = viral[:20]

        # STEP 2
        setstep(2, "Agent 2: Fetching trending topics from Google Trends...")
        trends, rising, realtime = {}, [], []
        try:
            pt = TrendReq(hl="en-IN", tz=330)
            for g in [
                ["nifty 50 today","banknifty","option trading","stock market india","sensex today"],
                ["algo trading","technical analysis","candlestick","rsi indicator","backtest"]
            ]:
                try:
                    pt.build_payload(g, timeframe="now 7-d", geo="IN")
                    df = pt.interest_over_time()
                    if not df.empty:
                        for kw in g:
                            if kw in df.columns: trends[kw] = int(df[kw].mean())
                    await asyncio.sleep(1)
                except: pass
            trends = dict(sorted(trends.items(), key=lambda x: x[1], reverse=True))
            for topic in ["nifty 50", "option trading", "stock market"]:
                try:
                    pt.build_payload([topic], timeframe="now 7-d", geo="IN")
                    rel = pt.related_queries()
                    rdf = rel.get(topic, {}).get("rising")
                    if rdf is not None and not rdf.empty:
                        rising.extend(rdf["query"].head(3).tolist())
                    await asyncio.sleep(1)
                except: pass
            try:
                rt = pt.realtime_trending_searches(pn="IN")
                fw = ["stock","nifty","sensex","market","sebi","rbi","trading","share","invest","ipo"]
                for _, row in rt.iterrows():
                    if any(w in str(row.get("title","")).lower() for w in fw):
                        realtime.append(row.get("title",""))
            except: pass
        except: pass
        state["trending"] = trends
        state["rising"]   = list(set(rising))[:8]
        state["realtime"] = realtime[:5]

        # STEP 3
        setstep(3, "Agent 3: Transcribing top videos with Whisper...")
        wmodel = whisper.load_model("base")
        transcribed = []
        for i, reel in enumerate(viral[:3]):
            audio = f"/tmp/tv_{i}.mp3"
            try:
                opts = {
                    "format": "bestaudio/best", "outtmpl": f"/tmp/tv_{i}",
                    "postprocessors": [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"96"}],
                    "quiet": True, "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([reel["video_url"]])
                if os.path.exists(audio):
                    result = wmodel.transcribe(audio, language="en")
                    transcribed.append({**reel, "transcript": result["text"].strip()})
                    os.remove(audio)
                else:
                    transcribed.append({**reel, "transcript": reel.get("caption","")})
            except:
                transcribed.append({**reel, "transcript": reel.get("caption","")})
        state["transcribed"] = transcribed

        # STEP 4
        setstep(4, "AI Brain: Analysing content through TradeVed lens...")
        reels_text = ""
        for i, r in enumerate(transcribed):
            reels_text += f"\nVIDEO {i+1}: {r.get('title','')[:70]}\nCategory: {r.get('category','').upper()}\n{r.get('views',0):,} views\nTranscript: {r.get('transcript','')[:400]}\n---"
        trends_str = "\n".join([f"  {k}: {v}/100" for k,v in trends.items()])
        analysis = call_llm(f"""You are Head of Content Strategy at TradeVed — India's systematic trading education platform.
Audience: Retail traders 20-35 learning options, algo trading, backtesting, technical analysis.

=== VIRAL FINANCE VIDEOS ===
{reels_text}

=== GOOGLE TRENDS INDIA ===
{trends_str}
Rising: {', '.join(rising[:5])}

Give analysis with these sections:
## WHY THIS CONTENT WENT VIRAL
## TOP 3 TRENDING TRADING TOPICS THIS WEEK
## CONTENT FORMAT WINNING RIGHT NOW
## TOP 3 OPPORTUNITIES FOR TRADEVED
## WHAT TO AVOID""")
        state["analysis"] = analysis

        # STEP 5
        setstep(5, "AI Brain: Writing scripts, captions and hashtags...")
        content = call_llm(f"""You are TradeVed's Instagram content creator.
TradeVed = India's best systematic trading education platform.
Audience = Retail traders India 20-35 yrs.
Tone = Educational, empowering. Never hype.

=== ANALYSIS ===
{analysis}

Create exactly 3 Instagram Reel ideas. For EACH:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDEA [N]: [TITLE]
Topic: [specific trading topic]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY THIS WILL GO VIRAL:
HOOK (First 3 seconds):
FULL REEL SCRIPT:
[00:00] HOOK: ...
[00:08] SETUP: ...
[00:15] CONTENT: ...
[00:30] PAYOFF: ...
[00:40] CTA: follow TradeVed
ON-SCREEN TEXT:
CAPTION (120 words):
HASHTAGS (25):
BEST TIME TO POST:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")
        state["content"] = content
        state["status"]  = "done"
        state["step"]    = 6
        state["step_label"] = "Pipeline complete! 🎉"

    except Exception as e:
        state["status"] = "error"
        state["error"]  = str(e)

class RunRequest(BaseModel):
    llm_mode:     str = "gemini"
    gemini_key:   str = ""
    ollama_model: str = "llama3"

@app.post("/api/run")
async def run(req: RunRequest, background_tasks: BackgroundTasks):
    if state["status"] == "running":
        return {"error": "Already running"}
    state["llm_mode"]    = req.llm_mode
    state["gemini_key"]  = req.gemini_key
    state["ollama_model"]= req.ollama_model
    for k in ["viral_reels","rising","realtime","transcribed"]:
        state[k] = []
    state["trending"] = {}
    state["analysis"] = state["content"] = state["error"] = ""
    background_tasks.add_task(run_pipeline)
    return {"message": "Pipeline started"}

@app.get("/api/status")
async def get_status():
    return {
        "status": state["status"], "step": state["step"],
        "step_label": state["step_label"], "error": state["error"],
        "counts": {
            "viral_reels":  len(state["viral_reels"]),
            "trending":     len(state["trending"]),
            "transcribed":  len(state["transcribed"]),
            "has_analysis": len(state["analysis"]) > 0,
            "has_content":  len(state["content"])  > 0,
        }
    }

@app.get("/api/results")
async def get_results():
    return {k: state[k] for k in ["viral_reels","trending","rising","realtime","transcribed","analysis","content"]}

@app.get("/api/check-ollama")
async def check_ollama():
    """Check if Ollama is running on user's local machine"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"available": True, "models": models}
    except:
        return {"available": False, "models": []}
