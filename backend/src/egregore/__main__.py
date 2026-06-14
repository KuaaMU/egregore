"""Entry point for Egregore CLI.

Usage:
    uv run python -m egregore create "Topic" --providers chatgpt grok
    uv run python -m egregore list
    uv run python -m egregore send <id> "prompt"
"""

from egregore.cli.main import main

if __name__ == "__main__":
    main()
