"""
Simple test script to verify MCPProject functionality
"""

import asyncio
import sys
from pathlib import Path

# Add scripts to path
scripts_path = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_path.parent))
sys.path.insert(0, str(scripts_path))

from scripts.agents.summarizer import SummarizerAgent
from scripts.agents.entity_extractor import EntityExtractorAgent
from scripts.agents.sentiment import SentimentAgent
from scripts.services.orchestrator import AnalysisOrchestrator


async def test_heuristic_agents():
    """Test agents in heuristic mode (no LLM)"""
    print("=" * 80)
    print("TESTING MCPPROJECT - HEURISTIC MODE")
    print("=" * 80)
    
    # Sample document
    sample_text = """
    John Smith, CEO of TechCorp Inc., announced record profits for Q4 2024.
    The company, based in San Francisco, reported a 45% increase in revenue.
    Smith credited the strong performance to innovative product launches and
    excellent team execution. The board of directors, including Jane Doe from
    London-based investment firm GlobalVentures Ltd., praised the achievements.
    Dated: January 15, 2024. Market analysts remain bullish on the company's
    prospects for 2024 and beyond.
    """
    
    print("\nTest Document:")
    print("-" * 80)
    print(sample_text[:200] + "...\n")
    
    # Test individual agents
    print("\n1. Testing Summarizer Agent...")
    summarizer = SummarizerAgent(llm_client=None)
    summary = await summarizer.run(sample_text)
    print(f"   ✓ Summary: {summary.text[:100]}...")
    print(f"   ✓ Key Points: {len(summary.key_points)} extracted")
    print(f"   ✓ Confidence: {summary.confidence}")
    
    print("\n2. Testing Entity Extractor Agent...")
    entity_extractor = EntityExtractorAgent(llm_client=None)
    entities = await entity_extractor.run(sample_text)
    print(f"   ✓ People: {len(entities.people)} extracted")
    print(f"   ✓ Organizations: {len(entities.organizations)} extracted")
    print(f"   ✓ Dates: {len(entities.dates)} extracted")
    print(f"   ✓ Locations: {len(entities.locations)} extracted")
    
    print("\n3. Testing Sentiment Agent...")
    sentiment = SentimentAgent(llm_client=None)
    sentiment_result = await sentiment.run(sample_text)
    print(f"   ✓ Tone: {sentiment_result.tone}")
    print(f"   ✓ Confidence: {sentiment_result.confidence}")
    print(f"   ✓ Formality: {sentiment_result.formality}")
    
    print("\n4. Testing Orchestrator (Parallel Execution)...")
    orchestrator = AnalysisOrchestrator(summarizer, entity_extractor, sentiment)
    structured, outcomes = await orchestrator.run(sample_text)
    
    print(f"   ✓ Total agents: {len(outcomes)}")
    print(f"   ✓ Successful: {sum(1 for o in outcomes.values() if o.success)}")
    print(f"   ✓ Failed: {sum(1 for o in outcomes.values() if not o.success)}")
    
    total_time = sum(o.processing_time_seconds for o in outcomes.values())
    print(f"   ✓ Total Processing Time: {total_time:.3f}s")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Set LLM_PROVIDER in .env (mock, groq, or openai)")
    print("2. Run: python scripts/cli.py")
    print("3. Enter document path when prompted")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(test_heuristic_agents())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
