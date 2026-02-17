#!/usr/bin/env python
"""
Entry point for MCPProject CLI - handles imports properly
"""

import sys
from pathlib import Path

# Add scripts directory to path so relative imports work
scripts_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_dir))

# Now run the CLI
if __name__ == "__main__":
    from cli import main
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        import logging
        logger = logging.getLogger("MCPProject-CLI")
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nFatal error: {e}")
        sys.exit(1)
