#!/bin/bash

# Quick start script for news automation

echo "🚀 News Automation - YouTube Shorts Generator"
echo "=============================================="
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Warning: Ollama doesn't seem to be running."
    echo "   Please start it with: ollama serve"
    echo ""
fi

# Check Python version
python3 --version

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing/updating dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "Usage:"
echo "  python main.py --type today          # Generate 'Today in 60 Seconds'"
echo "  python main.py --type topic          # Generate 'Hot Topic' video"
echo "  python main.py --type topic --topic 'AI'  # Generate video about specific topic"
echo ""

