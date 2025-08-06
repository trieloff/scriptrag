#!/usr/bin/env python3
"""Test script to check GitHub Models API access."""

import json
import os
import sys

import requests


def test_github_models_access(token: str | None = None) -> bool:
    """Test if we have access to GitHub Models API.

    Args:
        token: GitHub Personal Access Token. If not provided, will check
               environment variable GITHUB_TOKEN.

    Returns:
        True if access is successful, False otherwise.
    """
    # Get token from parameter or environment
    github_token = token or os.environ.get("GITHUB_TOKEN")

    if not github_token:
        print("❌ No GitHub token provided.")
        print("Please provide a token via:")
        print("  1. Environment variable: export GITHUB_TOKEN='your-token'")
        print("  2. Command line: python test_github_models.py 'your-token'")
        return False

    # GitHub Models API endpoint
    # Using the inference endpoint as mentioned in the blog post
    api_url = "https://models.inference.ai.azure.com"

    # Test with a simple model list request
    headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/json"}

    print("🔍 Testing GitHub Models access...")
    print(f"   API Endpoint: {api_url}")

    try:
        # Try to access the models endpoint
        response = requests.get(f"{api_url}/models", headers=headers, timeout=30)

        if response.status_code == 200:
            print("✅ Successfully connected to GitHub Models!")
            print(f"   Status Code: {response.status_code}")

            # Try to parse and show available models
            try:
                data = response.json()
                # Handle both possible response formats
                if isinstance(data, list):
                    models = data
                elif "data" in data:
                    models = data["data"]
                else:
                    models = []

                if models:
                    print(f"\n   📦 Total models available: {len(models)}")
                    print("\n   Available AI Models:")
                    print("   " + "=" * 70)

                    # Group models by publisher/provider
                    by_publisher: dict[str, list[dict[str, str]]] = {}
                    for model in models:
                        name = model.get("friendly_name") or model.get(
                            "name", "Unknown"
                        )
                        publisher = model.get("publisher", "Unknown")
                        task = model.get("task", "")
                        model_id = model.get("id", "")

                        if publisher not in by_publisher:
                            by_publisher[publisher] = []
                        by_publisher[publisher].append(
                            {"name": name, "task": task, "id": model_id}
                        )

                    # Display models grouped by publisher
                    for publisher in sorted(by_publisher.keys()):
                        print(f"\n   📂 {publisher}:")
                        for model in sorted(
                            by_publisher[publisher], key=lambda x: x["name"]
                        ):
                            task_str = f" ({model['task']})" if model["task"] else ""
                            print(f"      • {model['name']}{task_str}")
                else:
                    print("\n   No models found in response")
                    print("\n   Raw response (first 1000 chars):")
                    print(json.dumps(data, indent=2)[:1000])
            except Exception as e:
                print(f"   Response received but couldn't parse models: {e}")

            return True

        if response.status_code == 401:
            print("❌ Authentication failed (401 Unauthorized)")
            print("   Your token doesn't have access to GitHub Models.")
            print("   Please check:")
            print("   1. Your PAT has the required scopes")
            print(
                "   2. You have access to GitHub Models (might need to join waitlist)"
            )
            return False

        if response.status_code == 403:
            print("❌ Access forbidden (403 Forbidden)")
            print("   Your account doesn't have access to GitHub Models.")
            print("   You may need to:")
            print("   1. Join the GitHub Models waitlist")
            print("   2. Ensure your token has proper permissions")
            return False

        print(f"⚠️  Unexpected response: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return False

    except requests.exceptions.Timeout:
        print("❌ Request timed out. Check your internet connection.")
        return False

    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        print("   Could not reach GitHub Models API.")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main() -> int:
    """Main function to run the test."""
    print("=" * 60)
    print("GitHub Models Access Test")
    print("=" * 60)
    print()

    # Check if token was provided as command line argument
    token = None
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print("📝 Using token from command line argument")
    elif os.environ.get("GITHUB_TOKEN"):
        print("📝 Using token from GITHUB_TOKEN environment variable")
    else:
        print("⚠️  No token provided")

    print()
    success = test_github_models_access(token)

    print()
    print("=" * 60)
    if success:
        print("🎉 You have access to GitHub Models!")
    else:
        print("😔 Access to GitHub Models not available")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
