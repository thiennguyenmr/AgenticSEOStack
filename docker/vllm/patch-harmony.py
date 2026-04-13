"""
Patch vLLM GPT-OSS harmony mode to handle OpenClaw tool_calls messages.

Fixes:
- harmony_utils.py: handle content=None in assistant messages (tool_calls)
- serving_chat.py: skip role="tool" messages that harmony can't parse

Usage: python3 patch-harmony.py
"""

import sys

HARMONY_PATH = "/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/harmony_utils.py"
SERVING_PATH = "/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/serving_chat.py"

# Patch 1: harmony_utils.py
HARMONY_OLD = '''    if isinstance(content, str):
        contents = [TextContent(text=content)]
    else:
        # TODO: Support refusal.
        contents = [TextContent(text=c["text"]) for c in content]'''

HARMONY_NEW = '''    if content is None:
        contents = [TextContent(text="")]
    elif isinstance(content, str):
        contents = [TextContent(text=content)]
    else:
        # TODO: Support refusal.
        contents = [TextContent(text=c["text"]) for c in content if c is not None and "text" in c]
        if not contents:
            contents = [TextContent(text="")]'''

# Patch 2: serving_chat.py
SERVING_OLD = '''        # Add user message.
        for chat_msg in request.messages:
            messages.append(parse_chat_input(chat_msg))'''

SERVING_NEW = '''        # Add user message (skip tool role messages that harmony can't handle).
        for chat_msg in request.messages:
            msg_dict = chat_msg if isinstance(chat_msg, dict) else chat_msg.model_dump()
            if msg_dict.get("role") == "tool":
                continue
            messages.append(parse_chat_input(msg_dict))'''


def patch_file(path, old, new, name):
    with open(path) as f:
        code = f.read()
    if new in code:
        print(f"[SKIP] {name} already patched")
        return True
    if old not in code:
        print(f"[FAIL] {name} pattern not found - vLLM version may have changed")
        return False
    code = code.replace(old, new)
    with open(path, "w") as f:
        f.write(code)
    print(f"[OK]   {name} patched")
    return True


if __name__ == "__main__":
    r1 = patch_file(HARMONY_PATH, HARMONY_OLD, HARMONY_NEW, "harmony_utils.py")
    r2 = patch_file(SERVING_PATH, SERVING_OLD, SERVING_NEW, "serving_chat.py")
    sys.exit(0 if (r1 and r2) else 1)
