from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDER_SDKS = {"litellm", "openai", "groq", "anthropic", "azure", "twilio"}
ONLY_PLACE = ROOT / "agent" / "router.py"
CHANNEL_EXEMPT = ROOT / "actions" / "channels"
PACKAGES = ("core", "analysis", "agent", "watch", "actions", "api", "sanket_mcp")
EXEMPT_PARTS = ("forked", "board", ".venv", "notebooks")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def test_only_router_names_a_provider() -> None:
    offenders: list[str] = []
    for package in PACKAGES:
        for path in (ROOT / package).rglob("*.py"):
            if any(part in EXEMPT_PARTS for part in path.parts):
                continue
            if path == ONLY_PLACE or CHANNEL_EXEMPT in path.parents:
                continue
            leaked = _imports(path) & PROVIDER_SDKS
            if leaked:
                offenders.append(f"{path.relative_to(ROOT)} imports {sorted(leaked)}")
    assert not offenders, "only agent/router.py may import a provider SDK:\n" + "\n".join(offenders)


def test_router_declares_one_deployment_per_lane() -> None:
    from agent.router import DEPLOYMENT_OF, DEPLOYMENTS

    assert len(DEPLOYMENT_OF) == len(DEPLOYMENTS)


def test_planner_and_critic_are_different_model_families() -> None:
    from agent.router import DEPLOYMENT_OF

    planner = DEPLOYMENT_OF["sanket-plan"].model
    critic = DEPLOYMENT_OF["sanket-critic"].model
    assert planner != critic
    assert planner.split("-")[0] != critic.split("-")[0]
