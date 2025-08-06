#!/usr/bin/env python3
"""Example usage of the multi-provider LLM client."""

import asyncio

from scriptrag.utils import LLMClient, LLMProvider


async def main() -> None:
    """Demonstrate LLM client usage."""
    print("ScriptRAG Multi-Provider LLM Client Demo")
    print("=" * 50)

    # Initialize client with automatic provider selection
    client = LLMClient()

    # Wait for provider selection
    await asyncio.sleep(0.5)

    # Check which provider is active
    current = client.get_current_provider()
    if current:
        print(f"✓ Active provider: {current.value}")
    else:
        print("✗ No provider available")
        print("\nPlease configure one of:")
        print("  - GITHUB_TOKEN for GitHub Models")
        print(
            "  - SCRIPTRAG_LLM_ENDPOINT and SCRIPTRAG_LLM_API_KEY for OpenAI-compatible"
        )
        print("  - Run in Claude Code environment for Claude SDK")
        return

    print()

    # List available models
    print("Available Models:")
    print("-" * 30)
    try:
        models = await client.list_models()
        for model in models[:5]:  # Show first 5 models
            caps = ", ".join(model.capabilities) if model.capabilities else "unknown"
            print(f"  • {model.id} ({model.provider.value})")
            print(f"    Capabilities: {caps}")
    except Exception as e:
        print(f"  Error listing models: {e}")

    print()

    # Test completion
    print("Test Completion:")
    print("-" * 30)
    try:
        response = await client.complete(
            messages=[
                {
                    "role": "user",
                    "content": "Write a tagline for ScriptRAG",
                }
            ],
            temperature=0.7,
        )

        if response.choices:
            content = response.choices[0].get("message", {}).get("content", "")
            print(f"  Response: {content}")
            print(f"  Provider: {response.provider.value}")
            if response.usage:
                print(f"  Tokens: {response.usage.get('total_tokens', 'N/A')}")
    except Exception as e:
        print(f"  Error: {e}")

    print()

    # Test embedding (if supported)
    print("Test Embedding:")
    print("-" * 30)
    try:
        # Check if any model supports embeddings
        embedding_models = [m for m in models if "embedding" in m.capabilities]
        if embedding_models:
            embed_response = await client.embed(
                text="A screenplay about artificial intelligence",
                model=embedding_models[0].id,
            )

            if embed_response.data:
                embedding = embed_response.data[0].get("embedding", [])
                print(f"  Embedding dimensions: {len(embedding)}")
                print(f"  Provider: {embed_response.provider.value}")
                if len(embedding) > 0:
                    print(f"  First 5 values: {embedding[:5]}")
        else:
            print("  No embedding models available")
    except NotImplementedError:
        print("  Current provider doesn't support embeddings")
    except Exception as e:
        print(f"  Error: {e}")

    print()

    # Test provider switching
    print("Provider Switching:")
    print("-" * 30)

    # Try switching to different providers
    for provider in [LLMProvider.GITHUB_MODELS, LLMProvider.OPENAI_COMPATIBLE]:
        if provider != current:  # Don't switch to current
            success = await client.switch_provider(provider)
            if success:
                print(f"  ✓ Switched to {provider.value}")
                break
            print(f"  ✗ {provider.value} not available")

    print("\n" + "=" * 50)
    print("Demo complete!")


if __name__ == "__main__":
    # Set up async event loop
    asyncio.run(main())
