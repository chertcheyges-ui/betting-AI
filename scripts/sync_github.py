"""Publish the dashboard and pipeline source to a GitHub snapshot branch."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
REMOTE = "https://github.com/chertcheyges-ui/betting-AI.git"
BRANCH = "codex/auto-sync"
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
SECRET_PATTERN = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    rb"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def git(cwd, *args):
    return subprocess.check_output(
        ["/usr/bin/git", *args], cwd=cwd, env=ENV, text=True, timeout=120
    ).strip()


def source_files():
    fixed = (".env.example", ".gitignore", "requirements.txt",
             "dashboard/README.md", "dashboard/package.json",
             "dashboard/.openai/hosting.json")
    files = [ROOT / name for name in fixed]
    for directory, pattern in (
        (".", "*.py"), ("agents", "*.py"), ("scripts", "*.py"),
        ("scripts", "*.sh"), ("launchd", "*.plist"),
        ("dashboard", "*.cjs"), ("dashboard/scripts", "*.mjs"),
        ("dashboard/worker", "*.mjs"),
    ):
        files.extend((ROOT / directory).glob(pattern))
    assets = ROOT / "dashboard/site-static"
    files.extend(path for path in assets.iterdir()
                 if path.suffix in {".js", ".css", ".html", ".svg"})
    for path in sorted(set(files)):
        if path.is_file() and not path.is_symlink() and path.resolve() == path:
            yield path


def local_secrets():
    path = ROOT / ".env"
    if not path.is_file():
        return []
    secrets = []
    for line in path.read_bytes().splitlines():
        name, _, value = line.partition(b"=")
        if any(word in name.upper() for word in (b"KEY", b"TOKEN", b"PASSWORD", b"SECRET")):
            value = value.strip().strip(b"'\x22")
            if len(value) >= 12:
                secrets.append(value)
    return secrets


def main():
    secrets = local_secrets()
    with TemporaryDirectory(prefix="betting-github-") as tmp:
        checkout = Path(tmp)
        refs = git(ROOT, "ls-remote", "--heads", REMOTE, BRANCH)
        git(checkout, "clone", "--quiet", "--depth=1", "--branch",
            BRANCH if refs else "main", REMOTE, ".")
        if not refs:
            git(checkout, "switch", "--quiet", "-c", BRANCH)
        for field, fallback in (
            ("user.name", "Betting AI Sync"),
            ("user.email", "betting-ai-sync@users.noreply.github.com"),
        ):
            try:
                value = git(ROOT, "config", "--get", field)
            except subprocess.CalledProcessError:
                value = fallback
            git(checkout, "config", field, value)
        paths = []
        for source in source_files():
            relative = source.relative_to(ROOT)
            data = source.read_bytes()
            if SECRET_PATTERN.search(data) or any(secret in data for secret in secrets):
                raise SystemExit(f"Проверка остановлена: возможный секрет в {relative}")
            dest = checkout / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            shutil.copymode(source, dest)
            paths.append(str(relative))
        git(checkout, "add", "--", *paths)
        if git(checkout, "diff", "--cached", "--name-only"):
            git(checkout, "commit", "--quiet", "-m", "Sync Betting AI source")
        if not refs or git(checkout, "rev-parse", "HEAD") != refs.split()[0]:
            git(checkout, "push", "--quiet", "origin", f"HEAD:refs/heads/{BRANCH}")
            print("Синхронизировано:", git(checkout, "rev-parse", "--short", "HEAD"))


if __name__ == "__main__":
    main()
