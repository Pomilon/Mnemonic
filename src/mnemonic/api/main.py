import os
import sys

# Ensure project root is in sys.path for absolute imports
sys.path.append(os.getcwd())

from fastapi import FastAPI, Request, Form, Body, Response, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.security import APIKeyCookie
from src.mnemonic.engine import MnemonicEngine
from src.mnemonic.aggregator.schema import ContentType
from src.mnemonic.refinement.summarizer import LocalSummarizer
from src.mnemonic.config import config
import json
import asyncio
import datetime
import uvicorn
from typing import List, Optional

app = FastAPI()
engine = MnemonicEngine()
summarizer = LocalSummarizer(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_BASE_URL)

# Admin Security Configuration
ADMIN_TOKEN = config.MNEMONIC_ADMIN_TOKEN
cookie_scheme = APIKeyCookie(name="admin_token", auto_error=False)

def check_admin(token: str = Depends(cookie_scheme)):
    if token != ADMIN_TOKEN:
        return False
    return True

# Set up templates and static files
templates = Jinja2Templates(directory="src/mnemonic/web/templates")
os.makedirs("src/mnemonic/web/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="src/mnemonic/web/static"), name="static")

# Telemetry Log Queue
log_queue = asyncio.Queue()

async def add_log(msg: str):
    time_str = datetime.datetime.now().strftime("%H:%M:%S")
    # Format as pure data for SSE, UI will handle styling
    await log_queue.put(f"[{time_str}] {msg}")

ICON_MAP = {
    ContentType.FACT: "book-open",
    ContentType.CODE: "code",
    ContentType.DEEP_DIVE: "layout",
    ContentType.VIDEO: "video",
    ContentType.DISCUSSION: "message-square",
    ContentType.TUTORIAL: "graduation-cap",
    ContentType.DATASET: "database",
    ContentType.NEWS: "newspaper",
    ContentType.DIAGRAM: "image",
    ContentType.AUDIO: "audio-lines"
}

COLOR_MAP = {
    ContentType.FACT: ("text-emerald-400", "bg-emerald-400/10", "border-emerald-400/20"),
    ContentType.CODE: ("text-cyan-400", "bg-cyan-400/10", "border-cyan-400/20"),
    ContentType.DEEP_DIVE: ("text-indigo-400", "bg-indigo-400/10", "border-indigo-400/20"),
    ContentType.VIDEO: ("text-rose-400", "bg-rose-400/10", "border-rose-400/20"),
    ContentType.DISCUSSION: ("text-amber-400", "bg-amber-400/10", "border-amber-400/20"),
    ContentType.TUTORIAL: ("text-orange-400", "bg-orange-400/10", "border-orange-400/20"),
    ContentType.DATASET: ("text-fuchsia-400", "bg-fuchsia-400/10", "border-fuchsia-400/20"),
    ContentType.NEWS: ("text-blue-400", "bg-blue-400/10", "border-blue-400/20"),
    ContentType.DIAGRAM: ("text-violet-400", "bg-violet-400/10", "border-violet-400/20"),
    ContentType.AUDIO: ("text-lime-400", "bg-lime-400/10", "border-lime-400/20")
}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    llm_available = await summarizer.check_availability()
    return templates.TemplateResponse(request, "index.html", {"llm_available": llm_available})

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, query: str = Form(...), offset: int = Form(0)):
    if offset == 0:
        await add_log(f"Received query: '{query}'")
        await add_log("Generating query embedding...")
    else:
        await add_log(f"Fetching more results for '{query}' (offset: {offset})")
    
    response = await engine.search(query, offset=offset)
    
    if offset == 0:
        if response.from_cache:
            await add_log(f"Cache Hit! Distance: {response.distance:.4f}")
        else:
            await add_log(f"Cache Miss. Meta-search yielded {len(response.results)} unique results.")
            await add_log("Semantic re-ranking completed.")
    else:
        await add_log(f"Appended {len(response.results)} new nodes to stream.")

    template = "results.html" if offset == 0 else "results_more.html"
    return templates.TemplateResponse(request, template, {
        "query": query, 
        "results": response.results,
        "from_cache": response.from_cache,
        "latency": f"{response.latency:.2f}",
        "distance": f"{response.distance:.4f}" if response.distance else None,
        "query_vector_json": json.dumps(response.query_vector),
        "offset": offset,
        "next_offset": offset + len(response.results),
        "icon_map": ICON_MAP,
        "color_map": COLOR_MAP
    })

@app.post("/feedback/reject", response_class=HTMLResponse)
async def reject(request: Request, query: str = Form(...), rejected_id: str = Form(...), query_vector: str = Form(...)):
    try:
        q_vec = json.loads(query_vector)
    except:
        await add_log("Error parsing query vector for recalibration.")
        return Response(status_code=400)
    
    await add_log(f"Rejection received for node: {rejected_id}")
    await add_log("Recalibrating semantic weights. Applying negative penalty...")
    
    response = await engine.feedback_rejection(query, rejected_id, q_vec)
    
    await add_log("Vector space recalibrated. Fresh search yielded refined result.")

    if response.results:
        res = response.results[0]
        return templates.TemplateResponse(request, "card_partial.html", {
            "query": query,
            "res": res,
            "query_vector_json": json.dumps(response.query_vector),
            "icon_map": ICON_MAP,
            "color_map": COLOR_MAP
        })
    return HTMLResponse("")

@app.post("/synthesize", response_class=HTMLResponse)
async def synthesize(request: Request, context: str = Form(...)):
    await add_log("Synthesizing context using local LLM...")
    try:
        items = json.loads(context)
        if not items:
            return "No items pinned to synthesize."
            
        summary = await summarizer.summarize("", context_items=items)
        await add_log("Synthesis complete.")
        return summary
    except Exception as e:
        await add_log(f"Synthesis failed: {str(e)}")
        return f"Error: {str(e)}"

@app.get("/telemetry")
async def telemetry(request: Request):
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    log_msg = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                    yield f"event: log\ndata: {log_msg}\n\n"
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            # Shutdown event
            pass
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Admin Dashboard Logic
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(request, "login.html", {"error": error})

@app.post("/login")
async def login(token: str = Form(...)):
    if token == ADMIN_TOKEN:
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(key="admin_token", value=token, httponly=True)
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, authenticated: bool = Depends(check_admin)):
    if not authenticated:
        return RedirectResponse(url="/login", status_code=303)
        
    table = engine.cache.table
    df = table.to_pandas()
    
    # Process dataframe for more useful stats
    queries_data = []
    if not df.empty:
        # Sort by timestamp desc
        df = df.sort_values(by="timestamp", ascending=False)
        for _, row in df.iterrows():
            queries_data.append({
                "query": row["query"],
                "rejection_score": int(row["rejection_score"]),
                "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(row["timestamp"], "strftime") else str(row["timestamp"]),
                # Briefly show how many results are cached
                "result_count": len(json.loads(row["results_json"]))
            })

    stats = {
        "count": len(df),
        "rejections": int(df["rejection_score"].sum()) if not df.empty else 0,
        "queries": queries_data
    }
    return templates.TemplateResponse(request, "admin.html", {"stats": stats})

@app.post("/admin/reset", response_class=HTMLResponse)
async def admin_reset(request: Request, authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await add_log("Admin action: Resetting semantic cache...")
    engine.cache.clear_cache()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/delete-query", response_class=HTMLResponse)
async def admin_delete_query(request: Request, query: str = Form(...), authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    await add_log(f"Admin action: Deleting query '{query}' from cache.")
    escaped_query = query.replace("'", "''")
    engine.cache.table.delete(f"query = '{escaped_query}'")
    return RedirectResponse(url="/admin", status_code=303)

if __name__ == "__main__":
    try:
        uvicorn.run("src.mnemonic.api.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
    except KeyboardInterrupt:
        print("\n[Mnemonic] Process interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[Mnemonic] Unexpected error: {e}")
        sys.exit(1)
