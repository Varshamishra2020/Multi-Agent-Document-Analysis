"""
Multi-Agent Document Analysis System - Terminal CLI
Terminal-based interface for document analysis using multiple specialized agents.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Setup logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler("orchestration.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MCPProject-CLI")

# Load environment variables
load_dotenv()

# Import our modular agents and orchestrator
from agents.summarizer import SummarizerAgent
from agents.entity_extractor import EntityExtractorAgent
from agents.sentiment import SentimentAgent
from services.orchestrator import AnalysisOrchestrator
from utils.document_parser import extract_text, UnsupportedDocumentError
from models import AnalysisResults, EntitiesPayload, SentimentPayload, SummaryPayload, EntityItem


def _build_llm() -> Optional[object]:
    """Initialize LLM client based on environment configuration."""
    llm_provider = os.getenv("LLM_PROVIDER", "mock").lower()
    
    if llm_provider == "mock":
        logger.info("Using mock/heuristic mode for agents")
        return None
    
    if llm_provider == "groq":
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not groq_api_key:
            logger.warning("GROQ_API_KEY not set, falling back to heuristic mode")
            return None
        
        try:
            from langchain_groq import ChatGroq
            logger.info("Initializing Groq LLM client...")
            return ChatGroq(
                api_key=groq_api_key,
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                timeout=45,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Groq: {e}, falling back to heuristics")
            return None
    
    if llm_provider == "openai":
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not openai_api_key:
            logger.warning("OPENAI_API_KEY not set, falling back to heuristic mode")
            return None
        
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Initializing OpenAI LLM client...")
            return ChatOpenAI(
                api_key=openai_api_key,
                model="gpt-4-turbo",
                temperature=0.2,
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}, falling back to heuristics")
            return None
    
    logger.info(f"Unknown LLM_PROVIDER '{llm_provider}', using heuristic mode")
    return None


async def analyze_document(file_path: str, llm_client: Optional[object] = None) -> dict:
    """
    Analyze a document using all three agents in parallel.
    
    Args:
        file_path: Path to document (PDF or TXT)
        llm_client: Optional LLM client for enhanced analysis
    
    Returns:
        Dictionary with analysis results
    """
    logger.info(f"Starting analysis of: {file_path}")
    
    try:
        # Extract document text
        document_text = extract_text(file_path)
        logger.info(f"Extracted {len(document_text)} characters from document")
        
        # Initialize agents
        summarizer = SummarizerAgent(llm_client=llm_client)
        entity_extractor = EntityExtractorAgent(llm_client=llm_client)
        sentiment_analyzer = SentimentAgent(llm_client=llm_client)
        
        # Create orchestrator and run analysis
        orchestrator = AnalysisOrchestrator(summarizer, entity_extractor, sentiment_analyzer)
        structured_results, agent_outcomes = await orchestrator.run(document_text)
        
        # Build response
        result = {
            "file": Path(file_path).name,
            "status": "completed",
            "results": structured_results,
            "agents_completed": sum(1 for o in agent_outcomes.values() if o.success),
            "agents_failed": sum(1 for o in agent_outcomes.values() if not o.success),
        }
        
        # Calculate total processing time
        total_time = sum(o.processing_time_seconds for o in agent_outcomes.values())
        result["total_processing_time_seconds"] = round(total_time, 3)
        
        logger.info(f"Analysis complete. Agents: {result['agents_completed']} successful, {result['agents_failed']} failed")
        return result
    
    except UnsupportedDocumentError as e:
        logger.error(f"Unsupported document type: {e}")
        return {
            "file": Path(file_path).name if file_path else "unknown",
            "status": "failed",
            "error": str(e)
        }
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return {
            "file": Path(file_path).name if file_path else "unknown",
            "status": "failed",
            "error": f"File not found: {file_path}"
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return {
            "file": Path(file_path).name if file_path else "unknown",
            "status": "failed",
            "error": str(e)
        }


def format_results(results: dict) -> str:
    """Format analysis results for terminal display."""
    output = []
    output.append("\n" + "="*80)
    output.append(f"DOCUMENT ANALYSIS RESULTS")
    output.append("="*80)
    
    output.append(f"\nFile: {results.get('file', 'unknown')}")
    output.append(f"Status: {results.get('status', 'unknown')}")
    
    if results.get('status') == 'failed':
        output.append(f"Error: {results.get('error', 'Unknown error')}")
        return "\n".join(output)
    
    output.append(f"Total Processing Time: {results.get('total_processing_time_seconds', 0)}s")
    output.append(f"Agents Completed: {results.get('agents_completed', 0)}")
    output.append(f"Agents Failed: {results.get('agents_failed', 0)}")
    
    results_data = results.get('results', {})
    
    # Summary
    if 'summary' in results_data:
        output.append("\n" + "-"*80)
        output.append("SUMMARY")
        output.append("-"*80)
        summary = results_data['summary']
        if isinstance(summary, dict):
            if 'error' in summary:
                output.append(f"Error: {summary['error']}")
            else:
                output.append(f"Text: {summary.get('text', 'N/A')}")
                if summary.get('key_points'):
                    output.append("\nKey Points:")
                    for point in summary['key_points'][:5]:
                        output.append(f"  • {point}")
                output.append(f"Confidence: {summary.get('confidence', 'N/A')}")
                output.append(f"Processing Time: {summary.get('processing_time_seconds', 0)}s")
    
    # Entities
    if 'entities' in results_data:
        output.append("\n" + "-"*80)
        output.append("ENTITIES EXTRACTED")
        output.append("-"*80)
        entities = results_data['entities']
        if isinstance(entities, dict):
            if 'error' in entities:
                output.append(f"Error: {entities['error']}")
            else:
                for entity_type in ['people', 'organizations', 'dates', 'locations']:
                    entity_list = entities.get(entity_type, [])
                    if entity_list:
                        output.append(f"\n{entity_type.upper()}:")
                        for entity in entity_list[:5]:
                            if isinstance(entity, dict):
                                output.append(f"  • {entity.get('name', 'N/A')} (mentions: {entity.get('mentions', 0)})")
                                if entity.get('context'):
                                    output.append(f"    Context: {entity['context'][:100]}...")
                output.append(f"Processing Time: {entities.get('processing_time_seconds', 0)}s")
    
    # Sentiment
    if 'sentiment' in results_data:
        output.append("\n" + "-"*80)
        output.append("SENTIMENT ANALYSIS")
        output.append("-"*80)
        sentiment = results_data['sentiment']
        if isinstance(sentiment, dict):
            if 'error' in sentiment:
                output.append(f"Error: {sentiment['error']}")
            else:
                output.append(f"Tone: {sentiment.get('tone', 'N/A')}")
                output.append(f"Confidence: {sentiment.get('confidence', 'N/A')}")
                output.append(f"Formality: {sentiment.get('formality', 'N/A')}")
                if sentiment.get('key_phrases'):
                    output.append("\nKey Phrases:")
                    for phrase in sentiment['key_phrases']:
                        output.append(f"  • {phrase}")
                output.append(f"Processing Time: {sentiment.get('processing_time_seconds', 0)}s")
    
    output.append("\n" + "="*80 + "\n")
    return "\n".join(output)


async def main():
    """Main CLI entry point."""
    logger.info("MCPProject - Multi-Agent Document Analysis System")
    logger.info(f"LLM Provider: {os.getenv('LLM_PROVIDER', 'mock')}")
    
    # Initialize LLM client once
    llm_client = _build_llm()
    
    # Check for command-line arguments
    if len(sys.argv) > 1:
        # Batch mode: analyze file specified on command line
        file_path = sys.argv[1]
        results = await analyze_document(file_path, llm_client)
        print(format_results(results))
        sys.exit(0 if results.get('status') == 'completed' else 1)
    
    # Interactive mode
    print("\n" + "="*80)
    print("MCPProject - Multi-Agent Document Analysis System")
    print("="*80)
    print("\nAnalyze documents using specialized AI agents:")
    print("  • Summarizer Agent: Extract key points and summaries")
    print("  • Entity Extractor: Identify people, organizations, dates, locations")
    print("  • Sentiment Analyzer: Determine tone and formality")
    print("\nSupported formats: PDF, TXT")
    print("-"*80)
    
    while True:
        try:
            print("\nEnter document path (or 'quit' to exit):")
            file_path = input("> ").strip()
            
            if file_path.lower() in ('quit', 'exit', 'q'):
                print("Exiting...")
                break
            
            if not file_path:
                print("Please enter a valid file path")
                continue
            
            results = await analyze_document(file_path, llm_client)
            print(format_results(results))
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting...")
            break
        except Exception as e:
            logger.error(f"Error in interactive mode: {e}", exc_info=True)
            print(f"\nError: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nFatal error: {e}")
        sys.exit(1)
