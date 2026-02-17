#!/bin/bash
# Multi-Agent Document Analysis System - Startup Script

set -e  # Exit on error

echo '==================================='
echo 'Multi-Agent Document Analysis System'
echo 'Starting Terminal CLI...'
echo '==================================='

# Load environment variables
if [ -f .env ]; then
    echo 'Loading environment from .env'
    source .env
else
    echo 'Warning: .env file not found. Using defaults.'
fi

# Run the terminal-based CLI
echo 'Starting Document Analysis CLI...'
python run.py

echo 'CLI terminated.'
    echo 'ERROR: MCP server failed to start'
    exit 1
fi

echo 'MCP server is ready'

# Run a test orchestration query
echo '==================================='
echo 'Running sample orchestration query...'
echo '==================================='

python scripts/orchestration.py <<EOF
What were the main performance improvements in Q3 and how do they impact the future roadmap?
exit
EOF

echo ''
echo '==================================='
echo 'System startup complete!'
echo '==================================='

# Keep container alive
wait
