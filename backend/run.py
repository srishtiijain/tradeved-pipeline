"""Run this file to start the TradeVed backend server"""
import uvicorn

if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════╗")
    print("║   TradeVed AI Pipeline — Backend          ║")
    print("╚══════════════════════════════════════════╝\n")
    print("✅ Backend running at http://localhost:8000")
    print("   Open frontend/index.html in your browser\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
