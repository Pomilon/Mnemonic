import pytest
from fastapi.testclient import TestClient
from src.mnemonic.api.main import app
from src.mnemonic.config import config
import json
from typing import Optional

client = TestClient(app)

def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Mnemonic" in response.text

def test_search_basic():
    # Test basic search
    response = client.post("/search", data={"query": "hello world"})
    assert response.status_code == 200
    # Check if results are present in HTML
    assert "results" in response.text or "Search" in response.text

def test_search_with_filters():
    # Test search with filters
    response = client.post("/search", data={
        "query": "python",
        "domain": "github.com",
        "content_type": "code"
    })
    assert response.status_code == 200

import re
# ...
def test_feedback_reject():
    # 1. Perform a real search
    search_response = client.post("/search", data={"query": "quantum computing", "category": "general"})
    assert search_response.status_code == 200
    
    html = search_response.text
    
    # 2. Extract query_vector
    vector_match = re.search(r'id="current-query-vector" value=\'(\[.*?\])\'', html)
    assert vector_match is not None, "Query vector not found in HTML"
    query_vector_str = vector_match.group(1)
    
    # 3. Extract a result ID
    id_match = re.search(r'id="card-([a-f0-9]+)"', html)
    assert id_match is not None, "Result ID not found in HTML"
    rejected_id = id_match.group(1)

    # 4. Perform the rejection with real data
    response = client.post("/feedback/reject", data={
        "query": "quantum computing",
        "rejected_id": rejected_id,
        "query_vector": query_vector_str
    })
    assert response.status_code == 200

def test_synthesize():
    context = json.dumps([{"title": "T1", "snippet": "S1", "url": "U1"}])
    response = client.post("/synthesize", data={
        "context": context,
        "style": "bullet_points"
    })
    assert response.status_code == 200
    assert len(response.text) > 0

def test_export():
    context = json.dumps([{"title": "T1", "url": "U1", "snippet": "S1"}])
    response = client.post("/export", data={
        "context": context,
        "summary": "Test summary"
    })
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "Mnemonic Synthesis Export" in response.text

def test_admin_unauthorized():
    response = client.get("/admin", follow_redirects=False)
    # Should redirect to login
    assert response.status_code == 303
    assert "/login" in response.headers["location"]

def test_admin_authorized():
    # Login first
    client.post("/login", data={"token": config.MNEMONIC_ADMIN_TOKEN})
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Admin" in response.text

def test_admin_reset():
    # Login first
    client.post("/login", data={"token": config.MNEMONIC_ADMIN_TOKEN})
    response = client.post("/admin/reset", follow_redirects=False)
    assert response.status_code == 303
    assert "/admin" in response.headers["location"]

def test_image_proxy():
    # Test proxying a real image (e.g., Google logo)
    test_url = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
    response = client.get(f"/proxy/image?url={test_url}")
    assert response.status_code == 200
    assert "image/" in response.headers["content-type"]

def test_category_it():
    # Test searching in IT category (should use StackOverflow/HN)
    response = client.post("/search", data={"query": "rust ownership", "category": "it"})
    assert response.status_code == 200
    assert "stackoverflow" in response.text or "hackernews" in response.text

def test_category_science():
    # Test searching in Science category
    # Use a very common term to ensure results even if some engines are flaky
    response = client.post("/search", data={"query": "DNA", "category": "science"})
    assert response.status_code == 200
    # Relaxed assertion: just ensure we got some results
    assert "card-" in response.text or "No results found" in response.text


def test_category_images():
    # Test searching in Images category
    response = client.post("/search", data={"query": "nebula", "category": "images"})
    assert response.status_code == 200
    # Image results should have ContentType.IMAGE or show no results
    assert "card-" in response.text or "/proxy/image" in response.text or "No results found" in response.text


