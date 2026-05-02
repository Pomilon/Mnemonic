import pytest
from fastapi.testclient import TestClient
from src.mnemonic.api.main import app
import json

client = TestClient(app)

def test_citation_graph():
    # Mock results with vectors to ensure similarity is computed
    results = [
        {"id": "1", "title": "T1", "url": "U1", "snippet": "S1", "source": "src", "source_type": "live", "content_type": "fact", "is_ad": False, "vector": [0.1]*384},
        {"id": "2", "title": "T2", "url": "U2", "snippet": "S2", "source": "src", "source_type": "live", "content_type": "fact", "is_ad": False, "vector": [0.11]*384},
        {"id": "3", "title": "T3", "url": "U3", "snippet": "S3", "source": "src", "source_type": "live", "content_type": "fact", "is_ad": False, "vector": [-0.1]*384},
    ]
    response = client.post("/graph", data={"context": json.dumps(results)})
    assert response.status_code == 200
    assert "vis.Network" in response.text
    assert "nodes" in response.text
    assert "edges" in response.text

def test_hyde_activation():
    # This tests the endpoint, HyDE happens inside the engine.search
    # We check if the search still works with HyDE enabled.
    response = client.post("/search", data={"query": "explain quantum gravity"})
    assert response.status_code == 200

def test_session_persistence():
    # 1. Start a synthesis and get session id
    context = json.dumps([{"title": "T1", "url": "U1", "snippet": "S1", "source": "src", "source_type": "live", "content_type": "fact", "is_ad": False, "vector": [0.1]*384}])
    response = client.post("/synthesize", data={"context": context})
    assert response.status_code == 200
    
    # Extract session_id from the returned HTML
    import re
    match = re.search(r"data-id='([^']+)'", response.text)
    assert match, "Session ID not found in response"
    session_id = match.group(1)
    
    # 2. Chat in that session
    chat_response = client.post("/chat", data={"query": "Tell me more about it", "session_id": session_id})
    assert chat_response.status_code == 200
    assert len(chat_response.text) > 0
