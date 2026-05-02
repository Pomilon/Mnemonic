import os
import sys

# Ensure project root is in sys.path for absolute imports
sys.path.append(os.getcwd())

from fastapi import FastAPI, Request, Form, Body, Response, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.security import APIKeyCookie
from contextlib import asynccontextmanager
from src.mnemonic.engine import MnemonicEngine
from src.mnemonic.aggregator.schema import ContentType, ICON_MAP, COLOR_MAP, SearchCategory
from src.mnemonic.refinement.summarizer import LocalSummarizer
from src.mnemonic.config import config
from src.mnemonic.sessions import SessionManager
from src.mnemonic.refinement.graph import CitationGraphService
import json
import asyncio
import datetime
import uvicorn
import httpx
from typing import List, Optional

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await summarizer.close()

app = FastAPI(lifespan=lifespan)
engine = MnemonicEngine()
summarizer = LocalSummarizer()
session_manager = SessionManager()
graph_service = CitationGraphService(engine.ranker)

# Admin Security Configuration
ADMIN_TOKEN = config.MNEMONIC_ADMIN_TOKEN
cookie_scheme = APIKeyCookie(name="admin_token", auto_error=False)

def check_admin(token: str = Depends(cookie_scheme)):
    if token != ADMIN_TOKEN:
        return False
    return True

# Memory Index Logic moved to stats calculation in admin()

@app.get("/api/admin/config/app")
async def admin_get_app_config(authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
    from src.mnemonic.config import config
    return config.app

@app.post("/api/admin/config/app")
async def admin_update_app_config(new_config: dict = Body(...), authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
    from src.mnemonic.config import config
    try:
        config.save_app_config(new_config)
        await add_log("Admin update: General application settings updated.")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/config/llm")
async def admin_get_llm_config(authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
    config_path = os.path.join("src", "mnemonic", "aggregator", "llm_config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load LLM config: {str(e)}")

@app.post("/api/admin/config/llm")
async def admin_update_llm_config(new_config: dict = Body(...), authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
    config_path = os.path.join("src", "mnemonic", "aggregator", "llm_config.json")
    try:
        with open(config_path, "w") as f:
            json.dump(new_config, f, indent=2)
        summarizer.reload_config()
        await add_log(f"Admin update: LLM config changed to {new_config.get('provider')}")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/models/catalog")
async def admin_get_models_catalog(authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
    from src.mnemonic.models import model_manager
    return {
        "catalog": model_manager.catalog,
        "current": engine.ranker.model_name
    }

@app.post("/api/admin/models/add")
async def admin_add_model(
    model_id: str = Body(...),
    name: str = Body(...),
    description: str = Body(...),
    dimension: int = Body(...),
    authenticated: bool = Depends(check_admin)
):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
    from src.mnemonic.models import model_manager
    try:
        model_manager.add_model(model_id, name, description, dimension)
        await add_log(f"Admin action: New model added to catalog: {name} ({model_id})")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/models/select")
async def admin_select_model(model_name: str = Body(embed=True), authenticated: bool = Depends(check_admin)):
    if not authenticated:
        raise HTTPException(status_code=403, detail="Not authorized")
    from src.mnemonic.models import model_manager
    if model_name not in model_manager.catalog:
        raise HTTPException(status_code=400, detail="Model not in catalog")
    try:
        engine.ranker.update_model(model_name)
        # ... rest of persistence ...
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                cfg = json.load(f)
            cfg["SENTENCE_TRANSFORMER_MODEL"] = model_name
            with open("config.json", "w") as f:
                json.dump(cfg, f, indent=2)
        await add_log(f"Admin action: Embedding model switched to {model_name}")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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



@app.get("/", response_class=HTMLResponse)
async def home(request: Request, q: Optional[str] = None):
    llm_available = await summarizer.check_availability()
    return templates.TemplateResponse(request, "index.html", {
        "llm_available": llm_available,
        "initial_query": q
    })

@app.post("/search", response_class=HTMLResponse)
async def search(
    request: Request, 
    query: str = Form(...), 
    offset: int = Form(0), 
    category: str = Form("general"),
    domain: Optional[str] = Form(None), 
    content_type: Optional[str] = Form(None)
):
    # Map string category to Enum
    search_category = SearchCategory.GENERAL
    try:
        search_category = SearchCategory(category)
    except:
        pass

    filters = {}
    if domain: filters["domain"] = domain
    if content_type: filters["content_type"] = content_type
    
    if offset == 0:
        await add_log(f"Received query: '{query}' (Category: {category})")
        if filters:
            await add_log(f"Applying filters: {filters}")
        await add_log("Generating query embedding...")
    else:
        await add_log(f"Fetching more results for '{query}' (Category: {category}, offset: {offset})")
    
    response = await engine.search(query, offset=offset, filters=filters, category=search_category)
    
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
        "category": category,
        "results": response.results,
        "from_cache": response.from_cache,
        "latency": f"{response.latency:.2f}",
        "distance": f"{response.distance:.4f}" if response.distance else None,
        "query_vector_json": json.dumps(response.query_vector),
        "offset": offset,
        "next_offset": offset + len(response.results),
        "icon_map": ICON_MAP,
        "color_map": COLOR_MAP,
        "filters": filters
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
async def synthesize(request: Request, context: str = Form(...), style: str = Form("concise"), session_id: Optional[str] = Form(None)):
    await add_log(f"Synthesizing context using local LLM (style: {style})...")
    try:
        items = json.loads(context)
        if not items:
            return "No items pinned to synthesize."
        
        # Handle session and history
        history = []
        if session_id:
            history = session_manager.get_session_history(session_id)
        else:
            session_id = session_manager.create_session()
            
        summary = await summarizer.summarize("", context_items=items, style=style, history=history)
        
        # Save the turn to session
        session_manager.add_turn(
            session_id=session_id,
            role="assistant",
            content=summary,
            context=items
        )
        
        await add_log("Synthesis complete.")
        return f"<div class='session-id' data-id='{session_id}'>{summary}</div>"
    except Exception as e:
        await add_log(f"Synthesis failed: {str(e)}")
        return f"Error: {str(e)}"

@app.post("/export")
async def export_markdown(request: Request, context: str = Form(...), summary: str = Form("")):
    await add_log("Exporting synthesis to Markdown...")
    try:
        items = json.loads(context)
        if not items:
            return "No items pinned to export."
            
        # Generate Markdown content
        md = f"# Mnemonic Synthesis Export\n\n"
        if summary:
            md += f"## Summary\n{summary}\n\n"
            
        md += "## References\n\n"
        for item in items:
            md += f"- **[{item['title']}]({item['url']})**\n  {item['snippet']}\n\n"
            
        # Return as a downloadable file
        return Response(
            content=md, 
            media_type="text/markdown", 
            headers={"Content-Disposition": "attachment; filename=mnemonic_export.md"}
        )
    except Exception as e:
        await add_log(f"Export failed: {str(e)}")
        return f"Error: {str(e)}"

@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, query: str = Form(...), session_id: str = Form(...)):
    await add_log(f"Conversational follow-up: {query}")
    try:
        # 1. Get history
        history = session_manager.get_session_history(session_id)
        
        # 2. Perform search based on context if needed
        # For simplicity, we'll use the last context from the session
        last_turn = next((h for h in reversed(history) if h["context"]), None)
        context = last_turn["context"] if last_turn else []
        
        # Save user turn
        session_manager.add_turn(session_id, "user", query)
        
        # 3. Synthesize response
        response = await summarizer.summarize(
            text=query, 
            context_items=context, 
            style="concise", 
            history=history
        )
        
        session_manager.add_turn(session_id, "assistant", response)
        
        return response
    except Exception as e:
        await add_log(f"Chat failed: {str(e)}")
        return f"Error: {str(e)}"

@app.post("/graph", response_class=HTMLResponse)
async def get_graph(request: Request, context: str = Form(...)):
    await add_log("Generating citation graph...")
    try:
        items = json.loads(context)
        # Convert dicts back to SearchResult objects for the service
        from src.mnemonic.aggregator.schema import SearchResult
        results = [SearchResult(**item) for item in items]
        
        graph_data = graph_service.compute_graph(results)
        
        # Return a small HTML snippet that includes the vis-network JS and the graph
        return f"""
        <div id="mnemonic-graph" style="height: 400px; border: 1px solid #333; border-radius: 8px;"></div>
        <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <script>
            (function() {{
                const data = {json.dumps(graph_data)};
                const container = document.getElementById('mnemonic-graph');
                const options = {{
                    nodes: {{ shape: 'dot', size: 16, font: {{ color: '#eee' }} }},
                    edges: {{ color: '#666', smooth: {{ type: 'continuous' }} }},
                    physics: {{ stabilization: true }}
                }};
                new vis.Network(container, data, options);
            }})();
        </script>
        """
    except Exception as e:
        await add_log(f"Graph generation failed: {str(e)}")
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
                "result_count": len(json.loads(row["results_json"]))
            })
    
    # Compute analytics
    all_domains = {}
    total_rejections = 0
    rejection_count = 0
    
    if not df.empty:
        for _, row in df.iterrows():
            try:
                results = json.loads(row["results_json"])
                for res in results:
                    domain = res.get("url", "").split("//")[-1].split("/")[0]
                    if domain:
                        all_domains[domain] = all_domains.get(domain, 0) + 1
            except:
                continue
            
            if row["rejection_score"] > 0:
                total_rejections += row["rejection_score"]
                rejection_count += 1
                
        top_domains = dict(sorted(all_domains.items(), key=lambda x: x[1], reverse=True)[:10])
    else:
        top_domains = {}

    analytics = {
        "avg_results": float(df["results_json"].apply(lambda x: len(json.loads(x))).mean()) if not df.empty else 0,
        "top_queries": df["query"].value_counts().head(5).to_dict() if not df.empty else {},
        "rejection_rate": (df["rejection_score"] > 0).mean() * 100 if not df.empty else 0,
        "avg_rejection_score": total_rejections / rejection_count if rejection_count > 0 else 0,
        "top_domains": top_domains
    }

    stats = {
        "count": len(df),
        "rejections": int(df["rejection_score"].sum()) if not df.empty else 0,
        "queries": queries_data,
        "analytics": analytics
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

@app.get("/proxy/image")
async def proxy_image(url: str):
    """Proxies images to prevent direct client-side tracking."""
    # ... existing implementation ...
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, 
                headers={"User-Agent": engine.privacy.get_random_user_agent()},
                timeout=5.0,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch image")
                
            # Filter headers to only include safe ones
            safe_headers = {
                "Content-Type": response.headers.get("Content-Type", "image/jpeg"),
                "Cache-Control": "public, max-age=86400"
            }
            
            return Response(content=response.content, headers=safe_headers)
    except Exception as e:
        await add_log(f"Image proxy failed for {url}: {str(e)}")
        # Return a fallback pixel or error
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config/engines")
async def get_engines_config():
    config_path = "src/mnemonic/aggregator/engines.json"
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load engines config: {str(e)}")

@app.post("/api/config/engines")
async def update_engines_config(new_config: dict = Body(...)):
    config_path = "src/mnemonic/aggregator/engines.json"
    try:
        with open(config_path, "w") as f:
            json.dump(new_config, f, indent=2)
        
        # Reload engines in the aggregator
        engine.aggregator.reload_engines()
        await add_log("Search engines configuration updated and reloaded.")
        return {"status": "success"}
    except Exception as e:
        await add_log(f"Failed to update engines config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    try:
        uvicorn.run("src.mnemonic.api.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
    except KeyboardInterrupt:
        print("\n[Mnemonic] Process interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[Mnemonic] Unexpected error: {e}")
        sys.exit(1)
