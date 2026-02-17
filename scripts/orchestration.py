import os
import json
import logging
import time
import sys
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load configuration
load_dotenv()

# Logging configuration with file output
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler("orchestration.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("A2A-Orchestrator")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock") # Options: mock, openai, anthropic, etc.

logger.info(f"Configuration loaded - MCP_SERVER_URL: {MCP_SERVER_URL}, LLM_PROVIDER: {LLM_PROVIDER}")

from openai import OpenAI

# Initialize OpenAI client if key is available
client = None
if os.getenv("OPENAI_API_KEY"):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logger.info("OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")

class SpecialistAgent:
    """
    Specialist Agent (Synthesizer):
    Synthesizes a clear, concise answer based only on provided context.
    """
    def __init__(self, provider: str = "mock"):
        self.provider = provider
        self.system_prompt = (
            "You are a meticulous technical analyst. Your job is to synthesize a clear, "
            "concise answer based ONLY on the provided context and the user's question. "
            "If the information is not in the context, state that you don't know. "
            "Always cite your sources using [Filename] notation."
        )

    def synthesize(self, question: str, context: List[Dict[str, Any]]) -> str:
        logger.info(f"Specialist Agent: Synthesizing answer using {self.provider}...")
        
        if self.provider == "openai" and client:
            return self._openai_call(question, context)
        
        # Fallback to smart mock if openai is selected but no client exists
        return self._smart_mock_response(question, context)

    def _openai_call(self, question: str, context: List[Dict[str, Any]]) -> str:
        context_str = "\n\n".join([
            f"Source: {item['source']} (Relevance: {item.get('relevance', 'unknown')})\nSnippets:\n" + "\n".join(item['snippets'])
            for item in context
        ])
        
        final_prompt = f"CONTEXT:\n{context_str}\n\nQUESTION: {question}"
        logger.info(f"Specialist Agent: Sending final prompt to OpenAI (model: gpt-4-1106-preview)")
        logger.debug(f"Final prompt: {final_prompt[:500]}...")  # Log first 500 chars for debugging
        
        try:
            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": final_prompt}
                ],
                temperature=0.2
            )
            result = response.choices[0].message.content
            logger.info("Specialist Agent: Successfully received response from OpenAI")
            return result
        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            return self._smart_mock_response(question, context)

    def _smart_mock_response(self, question: str, context: List[Dict[str, Any]]) -> str:
        """
        A more intelligent mock that actually uses the retrieved snippets.
        Implements source grounding and citation functionality.
        """
        if not context:
            return "As a technical analyst, I have searched the available documentation but found no mention of these topics. [Source: None]"

        answer = "### Technical Synthesis\n\nBased on my analysis of the internal knowledge base:\n\n"
        
        citations = []
        # Group highlights by source
        for doc in context:
            source_name = doc['source']
            snippets = doc['snippets']
            relevance = doc.get('relevance', 'unknown')
            
            # Use the most relevant snippet to construct a sentence
            if snippets:
                # Basic cleaning of snippets for the response
                best_info = snippets[0].replace("#", "").strip()
                answer += f"- **From {source_name}** ({relevance} relevance): {best_info}\n"
                citations.append(source_name)
        
        # Add citation footer
        answer += f"\n---\n**Sources Consulted:** {', '.join(set(citations))}\n"
        answer += "*Note: This synthesis is grounded strictly in provided documentation to avoid hallucination.*"
        
        logger.info(f"Specialist Agent: Generated mock response with citations from {len(set(citations))} sources")
        return answer

class ManagerAgent:
    """
    Manager Agent (Orchestrator):
    Determines if tool is needed, calls it, and delegates to Specialist.
    
    Role: High-level orchestration, intent analysis, tool decision-making.
    Specialization: Strategic reasoning about when and what to retrieve.
    """
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.specialist = SpecialistAgent(provider=LLM_PROVIDER)
        logger.info(f"Manager Agent initialized with MCP URL: {mcp_url}")

    def handle_question(self, question: str):
        """Main orchestration flow."""
        logger.info(f"Manager Agent: Received user question: '{question}'")
        logger.info("Manager Agent: Step 1 - Intent Analysis")
        
        # Enhanced intent detection keywords
        trigger_keywords = [
            "performance", "architecture", "roadmap", "report", "pipeline", 
            "mmlu", "score", "latency", "metrics", "quantization", "future", 
            "transformer", "kafka", "flink", "snowflake", "k8s", "scaling",
            "optimization", "inference", "attention", "model", "data", "system"
        ]
        
        needs_retrieval = any(word in question.lower() for word in trigger_keywords)
        logger.info(f"Manager Agent: Intent analysis result - needs_retrieval={needs_retrieval}")
        
        context = []
        if needs_retrieval:
            logger.info("Manager Agent: Intent matched technical domain. Invoking MCP search...")
            start_time = time.time()
            context = self._call_retriever_tool(question)
            latency = time.time() - start_time
            logger.info(f"Manager Agent: MCP Retrieval completed in {latency:.4f}s with {len(context)} documents found.")
            logger.debug(f"Retrieved context: {json.dumps(context, indent=2)[:500]}...")  # Log sample
        else:
            logger.warning("Manager Agent: No technical context keywords detected. Proceeding without retrieval.")

        # Step 2: Log delegation
        logger.info(f"Manager Agent: Step 2 - Delegating to Specialist Agent for synthesis")
        
        # Delegate to Specialist
        final_answer = self.specialist.synthesize(question, context)
        
        self._print_formatted_answer(final_answer)
        logger.info("Manager Agent: Orchestration cycle complete")

    def _print_formatted_answer(self, answer: str):
        border = "=" * 60
        print(f"\n{border}")
        print(" " * 15 + "SPECIALIST ANALYST RESPONSE")
        print(border)
        print(answer)
        print(f"{border}\n")

    def _call_retriever_tool(self, query: str) -> List[Dict[str, Any]]:
        """Call the MCP server's document_retriever tool."""
        try:
            logger.debug(f"Calling MCP tool with query: {query}")
            response = requests.post(
                f"{self.mcp_url}/mcp/v1/invoke",
                json={
                    "tool": "document_retriever",
                    "arguments": {"query": query}
                },
                timeout=10
            )
            response.raise_for_status()
            raw_data = response.json()["content"][0]["text"]
            import ast
            parsed_results = ast.literal_eval(raw_data)
            logger.info(f"Successfully parsed {len(parsed_results)} results from MCP server")
            return parsed_results
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to MCP server at {self.mcp_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"MCP Tool invocation error: {e}")
            return []

def main():
    logger.info("=" * 60)
    logger.info("Multi-Agent Document Analysis System - A2A Orchestration")
    logger.info("=" * 60)
    
    import sys
    manager = ManagerAgent(MCP_SERVER_URL)
    
    if len(sys.argv) > 1:
        # CLI mode
        query = " ".join(sys.argv[1:])
        logger.info(f"Running in CLI mode with query: {query}")
        manager.handle_question(query)
        return

    print("\n" + "=" * 60)
    print(" " * 10 + "Multi-Agent Document Analysis System")
    print("=" * 60)
    print("Type 'exit' to quit.\n")
    
    # Pre-defined test question if user wants to see cross-document reasoning
    default_q = "What were the main performance improvements in Q3 and how do they impact the future roadmap?"
    print(f"💡 Example Question: {default_q}")
    print("\nThis question requires information from multiple documents to answer properly.")
    
    while True:
        print()
        user_input = input("📝 Enter your question: ").strip()
        if not user_input:
            continue
        if user_input.lower() == 'exit':
            logger.info("User requested exit. Shutting down.")
            print("\nGoodbye!")
            break
        
        logger.info("-" * 60)
        manager.handle_question(user_input)
        logger.info("-" * 60)

if __name__ == "__main__":
    main()
