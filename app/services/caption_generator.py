"""Caption generator service.

Generates engaging Instagram captions for products using a configurable
LLM provider (OpenAI, DeepSeek, or OpenRouter).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_CAPTION_PROMPT_TEMPLATE = """\
Create an engaging Instagram caption promoting a discounted product.

Product: {name}
Price: R$ {price:.2f}{discount_line}

Requirements:
- Include relevant emojis (3-5)
- Add a compelling call-to-action
- Use relevant hashtags (5-8)
- Keep it under 150 words
- Tone: enthusiastic, friendly

Return only the caption text, no extra commentary.
"""


class CaptionGenerator:
    """Generates Instagram captions via an LLM API.

    Supported providers:
        - ``"openai"``     – OpenAI Chat Completions API
        - ``"deepseek"``   – DeepSeek Chat API (OpenAI-compatible)
        - ``"openrouter"`` – OpenRouter proxy (OpenAI-compatible)
    """

    _PROVIDER_URLS = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/v1/chat/completions",
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    }

    _PROVIDER_MODELS = {
        "openai": "gpt-4o-mini",
        "deepseek": "deepseek-chat",
        "openrouter": "openai/gpt-4o-mini",
    }

    def __init__(self) -> None:
        self._settings = get_settings()
        self._provider = self._settings.llm_provider
        self._timeout = httpx.Timeout(30.0)

    async def generate(
        self,
        product_name: str,
        price: float,
        discount: float = 0.0,
    ) -> str:
        """Generate an Instagram caption for *product_name*.

        Args:
            product_name: Name / title of the product.
            price: Current price (used in the prompt).
            discount: Discount percentage, if any.

        Returns:
            Generated caption string, or a default fallback on failure.
        """
        prompt = self._build_prompt(product_name, price, discount)
        try:
            caption = await self._call_llm(prompt)
            logger.info("Caption generated (%d chars) via %s", len(caption), self._provider)
            return caption
        except Exception as exc:  # noqa: BLE001
            logger.error("Caption generation failed: %s", exc)
            return self._fallback_caption(product_name, price, discount)

    # ── LLM call ──────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        api_key = self._get_api_key()
        url = self._PROVIDER_URLS.get(self._provider, self._PROVIDER_URLS["openai"])
        model = self._settings.openai_model or self._PROVIDER_MODELS.get(
            self._provider, "gpt-4o-mini"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.8,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"].strip()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_api_key(self) -> str:
        """Return the API key for the configured provider."""
        mapping = {
            "openai": self._settings.openai_api_key,
            "deepseek": self._settings.deepseek_api_key,
            "openrouter": self._settings.openrouter_api_key,
        }
        key = mapping.get(self._provider, "")
        if not key:
            raise ValueError(
                f"No API key configured for LLM provider '{self._provider}'. "
                f"Set the corresponding environment variable."
            )
        return key

    @staticmethod
    def _build_prompt(name: str, price: float, discount: float) -> str:
        discount_line = f"\nDiscount: {discount:.0f}% OFF" if discount > 0 else ""
        return _CAPTION_PROMPT_TEMPLATE.format(
            name=name, price=price, discount_line=discount_line
        )

    @staticmethod
    def _fallback_caption(name: str, price: float, discount: float) -> str:
        """Return a simple caption when the LLM is unavailable."""
        if discount > 0:
            return (
                f"🔥 {name} por apenas R$ {price:.2f}! "
                f"{discount:.0f}% de desconto por tempo limitado. "
                f"Aproveite agora! 🛒 #desconto #oferta #compras"
            )
        return (
            f"✨ {name} – R$ {price:.2f}. "
            f"Qualidade garantida. Compre agora! 🛒 #produto #oferta"
        )
