import os
from dotenv import load_dotenv

load_dotenv()

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()

PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


def effective_provider() -> str:
    if LLM_PROVIDER and LLM_PROVIDER != "auto":
        return LLM_PROVIDER
    base = LLM_BASE_URL.lower()
    if "anthropic.com" in base:
        return "anthropic"
    if not base and LLM_MODEL.lower().startswith("claude"):
        return "anthropic"
    if "11434" in base:
        return "ollama"
    if "1234" in base:
        return "lmstudio"
    return "openai_compatible"


def effective_base_url() -> str:
    if LLM_BASE_URL:
        return LLM_BASE_URL
    return PROVIDER_BASE_URLS.get(effective_provider(), "")


def llm_enabled() -> bool:
    if not LLM_MODEL:
        return False
    provider = effective_provider()
    if provider in {"ollama", "lmstudio"} or bool(LLM_BASE_URL):
        return True
    return bool(LLM_API_KEY)
