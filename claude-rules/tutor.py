#!/usr/bin/env python3
"""
A command-line coding tutor powered by the Claude API.

Keeps conversation history so you can ask follow-up questions, streams
responses as they're written, and lets you load a source file into the chat.

Setup:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...      # your API key

Run:
    python tutor.py

Commands (type these at the prompt):
    /file <path>   Load a file's contents into your next message
    /reset         Start a fresh conversation (clears history)
    /effort <lvl>  Set reasoning depth: low | medium | high (default: medium)
    /help          Show this help
    /quit          Exit
"""

import os
import sys

import anthropic

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "You are a patient programming tutor helping me learn C and other "
    "languages. Your goal is to help me understand, not just to hand me "
    "working code.\n\n"
    "Guidelines:\n"
    "- Explain the WHY, not only the fix. Connect it to underlying concepts "
    "(memory, pointers, types, undefined behavior, control flow).\n"
    "- When I share buggy code, give me a hint first and ask whether I want "
    "the full solution before writing it out.\n"
    "- Call out undefined behavior, memory issues, and likely compiler "
    "warnings explicitly.\n"
    "- Keep examples small and focused. Prefer clear explanations over walls "
    "of code.\n"
    "- When I clearly ask for a complete solution, give it — then explain it."
)


def load_file(path: str) -> str | None:
    """Read a file and wrap it for the model, or return None on failure."""
    try:
        with open(os.path.expanduser(path), "r") as f:
            contents = f.read()
    except OSError as e:
        print(f"  [could not read {path}: {e}]")
        return None
    return f"Here is the contents of `{path}`:\n\n```\n{contents}\n```\n\n"


def read_user_input() -> str:
    """Read a possibly multi-line message. Blank line ends the message."""
    print("\nYou (blank line to send, /help for commands):")
    lines: list[str] = []
    while True:
        try:
            line = input("  ")
        except EOFError:  # Ctrl-D
            return "/quit"
        # A command on the first line is handled immediately.
        if not lines and line.startswith("/"):
            return line
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: set ANTHROPIC_API_KEY in your environment first.")
        sys.exit(1)

    client = anthropic.Anthropic()
    messages: list[dict] = []   # full conversation history (stateless API)
    effort = "medium"
    pending_file = ""           # file text queued by /file, prepended to next msg

    print("Claude coding tutor. Type /help for commands, /quit to exit.")

    while True:
        text = read_user_input().strip()
        if not text:
            continue

        # ---- commands ----
        if text in ("/quit", "/exit"):
            print("Happy coding!")
            break
        if text == "/help":
            print(__doc__)
            continue
        if text == "/reset":
            messages.clear()
            pending_file = ""
            print("  [conversation cleared]")
            continue
        if text.startswith("/effort"):
            parts = text.split()
            if len(parts) == 2 and parts[1] in ("low", "medium", "high"):
                effort = parts[1]
                print(f"  [effort set to {effort}]")
            else:
                print("  [usage: /effort low|medium|high]")
            continue
        if text.startswith("/file"):
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                loaded = load_file(parts[1])
                if loaded:
                    pending_file = loaded
                    print(f"  [loaded {parts[1]} — it'll be attached to your "
                          f"next message]")
            else:
                print("  [usage: /file <path>]")
            continue

        # ---- normal message ----
        user_content = pending_file + text
        pending_file = ""
        messages.append({"role": "user", "content": user_content})

        print("\nTutor:")
        assistant_reply = ""
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
                messages=messages,
            ) as stream:
                for chunk in stream.text_stream:
                    print(chunk, end="", flush=True)
                    assistant_reply += chunk
            print()
        except anthropic.APIError as e:
            print(f"\n  [API error: {e}]")
            messages.pop()  # drop the unanswered user turn so history stays valid
            continue

        messages.append({"role": "assistant", "content": assistant_reply})


if __name__ == "__main__":
    main()
