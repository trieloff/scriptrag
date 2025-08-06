#!/usr/bin/env python3
"""Test GitHub Models with OpenAI-compatible API."""

import json
import sys

import requests


def test_models(token: str) -> None:
    """Test GitHub Models using OpenAI-compatible endpoint."""
    # GitHub Models uses OpenAI-compatible API
    base_url = "https://models.inference.ai.azure.com"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("Testing GitHub Models API...")
    print(f"Base URL: {base_url}")
    print()

    # Try the OpenAI-compatible models endpoint
    try:
        response = requests.get(f"{base_url}/models", headers=headers, timeout=30)

        print(f"Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check if it's a list or has 'data' field
            if isinstance(data, list):
                models = data
            elif isinstance(data, dict) and "data" in data:
                models = data["data"]
            else:
                print("Unexpected response format:")
                print(json.dumps(data, indent=2)[:2000])
                return

            print(f"\n📦 Found {len(models)} models available:\n")
            print("=" * 80)

            # Group by provider/publisher
            by_provider: dict[str, list[str]] = {}
            for model in models:
                # Handle different response formats
                if isinstance(model, dict):
                    model_id = model.get("id", "")
                    name = model.get("name") or model.get("friendly_name", "")
                    publisher = model.get("publisher", "")

                    # Extract provider from ID if not in publisher field
                    if not publisher and "/" in model_id:
                        parts = model_id.split("/")
                        if len(parts) > 1:
                            publisher = (
                                parts[0]
                                .replace("azureml://registries/", "")
                                .replace("azureml-", "")
                            )

                    if not publisher:
                        publisher = "Other"

                    if publisher not in by_provider:
                        by_provider[publisher] = []

                    by_provider[publisher].append(name or model_id)

            # Display grouped models
            for provider in sorted(by_provider.keys()):
                print(f"\n{provider.upper()}:")
                for model_name in sorted(by_provider[provider]):
                    print(f"  • {model_name}")

        else:
            print(f"Failed with status: {response.status_code}")
            print(f"Response: {response.text[:500]}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        print("Usage: python test_github_models_openai.py <github_token>")
        sys.exit(1)

    test_models(token)
