"""
Thin wrapper around the OpenAI API client. Reads the API key from the
OPENAI_API_KEY environment variable (loaded from .env) -- never
hardcoded, never passed as a literal in any call site.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
import openai

load_dotenv()


class MissingApiKeyError(Exception):
    def __init__(self):
        super().__init__(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it before calling any LLM-backed function."
        )


def get_client() -> openai.OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise MissingApiKeyError()
    return openai.OpenAI(api_key=api_key)