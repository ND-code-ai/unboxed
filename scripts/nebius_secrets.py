"""Put the deployment's keys in SecretStash, for the developer to run once in a terminal
(docs/building_the_project.md, "Deployment"). No value is printed or put on a Windows command
line: the keys come from .env, the registry token from a prompt, and both reach the CLI in WSL
through stdin.

uv run python scripts/nebius_secrets.py --project <project id> --github-user <login>

A new registry token, with the other keys left as they are:

uv run python scripts/nebius_secrets.py --github-user <login> --replace-registry <secret id>
"""

import argparse
import asyncio
import getpass
import json
import subprocess

import httpx

from shopper.config import (
    FIRECRAWL_KEY_NAME,
    LANGSMITH_KEY_NAME,
    NEBIUS_KEY_NAME,
    TAVILY_KEY_NAME,
    load_env,
    require,
)

KEYS_SECRET = "true-cost-keys"
REGISTRY_SECRET = "true-cost-registry"
# Settings cannot change after an endpoint is created, so eBay's are passed before task 2.2 uses
# them; a later key would mean a new endpoint and a new URL.
APP_KEYS = (
    NEBIUS_KEY_NAME,
    TAVILY_KEY_NAME,
    FIRECRAWL_KEY_NAME,
    LANGSMITH_KEY_NAME,
    "EBAY_CLIENT_ID",
    "EBAY_CLIENT_SECRET",
)
NEBIUS = "$HOME/.nebius/bin/nebius"
CREATE = (
    f'{NEBIUS} mysterybox secret create --name "$1" --parent-id "$2" '
    '--secret-version-set-primary --secret-version-payload "$(cat)"'
)
ADD_VERSION = (
    f'{NEBIUS} mysterybox secret-version create --parent-id "$1" --set-primary --payload "$(cat)"'
)


def stored(command: str, targets: list[str], label: str, values: dict[str, str]) -> None:
    """Run the CLI command with these keys and values on stdin; what the CLI says goes to the
    terminal only on a failure, with any value in it masked."""
    payload = [{"key": key, "string_value": value} for key, value in values.items()]
    # --exec, as `wsl --` runs the command through a shell first, which strips the JSON's quotes.
    done = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--exec", "bash", "-c", command, "store", *targets],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        said = done.stderr
        for value in values.values():
            said = said.replace(value, "***")
        raise SystemExit(f"{label} was not stored:\n{said}")
    print(f"{label} stored with: {', '.join(values)}")


async def github_user(token: str) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "true-cost-copilot"},
        )


def asked_token(user: str) -> str:
    """The registry token from a prompt, refused unless GitHub says it is this user's and can read
    packages, so a slip in pasting it is found here and not at the endpoint's create."""
    token = getpass.getpass("GitHub classic token with only read:packages (input hidden): ").strip()
    answer = asyncio.run(github_user(token))
    if answer.status_code != 200:
        raise SystemExit(f"GitHub answered {answer.status_code} for this token; nothing stored.")
    login = answer.json()["login"]
    scopes = answer.headers.get("x-oauth-scopes", "")
    if login.lower() != user.lower() or "read:packages" not in scopes:
        raise SystemExit(f"This token is {login}'s, with scopes [{scopes}]; nothing stored.")
    return token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--github-user", required=True)
    parser.add_argument("--replace-registry", metavar="SECRET_ID")
    arguments = parser.parse_args()
    if arguments.replace_registry is None and arguments.project is None:
        parser.error("--project is needed to create the secrets")

    if arguments.replace_registry is None:
        env = load_env()
        keys = {name: require(env, name) for name in APP_KEYS}
        stored(CREATE, [KEYS_SECRET, arguments.project], KEYS_SECRET, keys)
    token = asked_token(arguments.github_user)
    # The Nebius docs spell these keys two ways; both are stored.
    registry = {
        "REGISTRY_USERNAME": arguments.github_user,
        "REGISTRY_PASSWORD": token,
        "registry_username": arguments.github_user,
        "registry_password": token,
    }
    if arguments.replace_registry is None:
        stored(CREATE, [REGISTRY_SECRET, arguments.project], REGISTRY_SECRET, registry)
    else:
        stored(ADD_VERSION, [arguments.replace_registry], REGISTRY_SECRET, registry)


if __name__ == "__main__":
    main()
