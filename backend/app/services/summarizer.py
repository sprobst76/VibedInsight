from pathlib import Path

import ollama

from app.config import settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template from file."""
    prompt_file = PROMPTS_DIR / f"{name}.txt"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt template '{name}' not found")


async def generate_summary(text: str, language: str = "auto") -> str:
    """
    Generate a summary of the given text using Ollama.
    """
    prompt_template = load_prompt("summary")
    prompt = prompt_template.format(text=text[:8000])  # Limit input length

    client = ollama.AsyncClient(host=settings.ollama_base_url)

    response = await client.chat(
        model=settings.ollama_model,
        messages=[{"role": "user", "content": prompt}],
    )

    return response["message"]["content"]


async def extract_topics(text: str, existing_topics: list[str] | None = None) -> list[str]:
    """
    Extract topics/tags from text using Ollama.
    """
    prompt_template = load_prompt("topics")
    existing = ", ".join(existing_topics) if existing_topics else "none"
    prompt = prompt_template.format(text=text[:4000], existing_topics=existing)

    client = ollama.AsyncClient(host=settings.ollama_base_url)

    response = await client.chat(
        model=settings.ollama_model,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse response - expect comma-separated topics
    content = response["message"]["content"]
    topics = [t.strip().lower() for t in content.split(",") if t.strip()]

    # Clean up and deduplicate
    return list(set(topics))[:10]  # Max 10 topics
