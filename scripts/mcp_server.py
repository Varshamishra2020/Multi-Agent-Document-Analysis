import os
import glob
import logging
import time
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MCP-Server")

app = FastAPI(title="Knowledge Retriever MCP Server")

# Basic Knowledge Base setup
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Configuration from environment
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", 8000))

class ToolInvokeRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any]

def get_kb_content() -> List[Dict[str, str]]:
    documents = []
    for filepath in glob.glob(os.path.join(KB_DIR, "*.md")):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            documents.append({
                "source": os.path.basename(filepath),
                "content": content
            })
    return documents

def search_documents(query: str, max_snippets: int = 5) -> List[Dict[str, Any]]:
    """
    Search documents using keyword-based relevance scoring.
    Returns a list of documents with matching snippets and metadata for citation.
    """
    logger.info(f"Searching documents for query: '{query}'")
    start_time = time.time()
    
    docs = get_kb_content()
    results = []
    
    # Process query: remove stop words, small words, and prep terms
    query = query.lower()
    query_terms = [t for t in query.split() if len(t) > 2]
    
    if not query_terms:
        logger.warning("Query contains no significant terms after filtering")
        return []
    
    for doc in docs:
        content = doc["content"]
        content_lower = content.lower()
        
        # Calculate score based on term frequency and phrase matching
        score = 0
        for term in query_terms:
            score += content_lower.count(term)
            
        # Bonus for exact query match
        if query in content_lower:
            score += 10
            
        if score > 0:
            # Splitting by paragraphs and finding relevant ones
            # Use paragraphs or sections (marked by #)
            sections = content.split("\n")
            relevant_snippets = []
            
            # Find lines containing any of the terms
            for line in sections:
                line = line.strip()
                if not line: continue
                
                line_lower = line.lower()
                if any(term in line_lower for term in query_terms):
                    relevant_snippets.append(line)
                    
            # Limit snippets and ensure we include the most relevant ones
            # Sort snippets by how many query terms they contain
            relevant_snippets.sort(key=lambda s: sum(1 for t in query_terms if t in s.lower()), reverse=True)
            
            results.append({
                "source": doc["source"],
                "score": score,
                "snippets": list(dict.fromkeys(relevant_snippets))[:max_snippets], # Deduplicate and limit
                "relevance": "high" if score > 10 else "medium" if score > 5 else "low"
            })
            
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    elapsed_time = time.time() - start_time
    logger.info(f"Search completed in {elapsed_time:.4f}s. Found {len(results)} relevant documents.")
    
    return results

@app.get("/mcp/v1/tools")
def get_tools():
    """
    Returns the list of tools provided by this MCP server.
    """
    return {
        "tools": [
            {
                "name": "document_retriever",
                "description": "Searches the internal knowledge base for technical documents and returns relevant snippets.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant documents."
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    }

@app.post("/mcp/v1/invoke")
def invoke_tool(request: ToolInvokeRequest):
    """
    Invokes a tool by name with the provided arguments.
    MCP Protocol v1 compliant endpoint for tool execution.
    """
    logger.info(f"Tool invocation request: {request.tool} with args: {request.arguments}")
    
    if request.tool == "document_retriever":
        query = request.arguments.get("query")
        if not query:
            logger.error("Missing 'query' argument in document_retriever call")
            raise HTTPException(status_code=400, detail="Missing 'query' argument")
        
        results = search_documents(query)
        logger.info(f"Returning {len(results)} results for tool invocation")
        return {"content": [{"type": "text", "text": str(results)}]}
    
    logger.error(f"Tool '{request.tool}' not found")
    raise HTTPException(status_code=404, detail=f"Tool '{request.tool}' not found")

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    logger.debug("Health check requested")
    return {"status": "healthy", "service": "Knowledge Retriever MCP Server"}

if __name__ == "__main__":
    logger.info(f"Starting MCP Knowledge Retriever Server on {MCP_SERVER_HOST}:{MCP_SERVER_PORT}")
    logger.info(f"Knowledge Base Directory: {KB_DIR}")
    uvicorn.run(app, host=MCP_SERVER_HOST, port=MCP_SERVER_PORT, log_level="info")
