# TradeVed AI Content Pipeline

> Multi-agent AI system that finds viral finance content on YouTube, analyses why it worked, and writes ready-to-film Instagram Reel scripts for TradeVed — India's systematic trading education platform.

---

## What It Does

Every run, the pipeline automatically:
1. **Agent 1** — Finds viral trading videos on YouTube (views, likes, engagement rate)
2. **Agent 2** — Fetches trending finance topics in India via Google Trends
3. **Agent 3** — Transcribes top videos using OpenAI Whisper
4. **AI Brain** — Analyses why content went viral through a TradeVed lens
5. **Content Gen** — Writes 3 full Instagram Reel scripts with hooks, captions, hashtags

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| FastAPI | Backend API server |
| yt-dlp | YouTube scraping (no login needed) |
| OpenAI Whisper | Local audio transcription |
| Ollama + gemma:2b | Local LLM inference (zero API cost) |
| Google Gemini API | Cloud LLM option (free tier) |
| pytrends | Google Trends India data |
| Vanilla JS + Chart.js | Frontend UI |

---

## Setup

**Requirements:**
- Python 3.10+
- ffmpeg
- Ollama

**1. Install ffmpeg**
```bash
winget install ffmpeg
```

**2. Install Python dependencies**
```bash
cd backend
pip install -r requirements.txt
```

**3. Install Ollama**

Download from [ollama.ai](https://ollama.ai) then pull a model:
```bash
ollama pull gemma:2b
```

---

## Run

**Terminal 1 — Start Ollama:**
```bash
ollama serve
```

**Terminal 2 — Start backend:**
```bash
cd backend
uvicorn main:app --reload
```

Open **http://localhost:8000**

---

## Usage

1. Select **Ollama** or **Gemini** as your AI model
2. If using Gemini — paste your free API key from [aistudio.google.com](https://aistudio.google.com)
3. If using Ollama — click **Retry Detection** to confirm it's running
4. Hit **Run Full Pipeline**
5. View results in the **Results** tab — viral videos, trends chart, content ideas
6. Click **Download All** to save everything as a `.txt` file

---

## Output

Every run produces:
- Viral finance videos with views, likes, engagement stats
- Trending topics bar chart (Google Trends India)
- 3 Instagram Reel scripts each with:
  - Hook (first 3 seconds)
  - Full timestamped script
  - On-screen text overlays
  - 120-word caption
  - 25 hashtags
  - Best time to post

---

## Project Structure

```
frontend/
├── index.html              
  

backend/
├── main.py              # FastAPI server + all 5 pipeline agents
├── pipeline.py          # Pipeline logic (agents + LLM calls)
├── run.py               # Shortcut to start server
├── requirements.txt     # Python dependencies
     
```

