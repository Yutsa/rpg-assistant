from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
INGEST_CLJ_DIR = _REPO_ROOT / "packages" / "ingest-clj"
_LOCAL_JDK_ROOT = Path.home() / ".local" / "jdk"


def resolve_java_home() -> str | None:
    """Prefer JAVA_HOME, then Temurin JDK under ~/.local/jdk (see cloud-agent-install.sh)."""
    configured = os.environ.get("JAVA_HOME", "").strip()
    if configured and (Path(configured) / "bin" / "java").is_file():
        return configured
    if _LOCAL_JDK_ROOT.is_dir():
        for candidate in sorted(_LOCAL_JDK_ROOT.glob("jdk-*"), reverse=True):
            if (candidate / "bin" / "java").is_file():
                return str(candidate)
    return None


def clojure_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    java_home = resolve_java_home()
    if java_home:
        env["JAVA_HOME"] = java_home
        env["PATH"] = f"{java_home}/bin:{env.get('PATH', '')}"
    return env
