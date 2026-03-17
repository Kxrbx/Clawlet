"""Skill installation service decoupled from CLI/tool wrappers."""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from loguru import logger

from clawlet.workspace_layout import WorkspaceLayout


SKILL_METADATA_FILENAME = ".clawlet-skill-source.json"


@dataclass(slots=True)
class SkillInstallResult:
    success: bool
    message: str
    path: str = ""
    skill_name: str = ""
    github_url: str = ""


def parse_github_repo(github_url: str) -> tuple[bool, str, str, str]:
    text = str(github_url or "").strip()
    if not text:
        return False, "", "", "GitHub URL is required"

    if text.startswith("git@github.com:"):
        repo_part = text.split("git@github.com:", 1)[1].strip().rstrip("/")
        if repo_part.endswith(".git"):
            repo_part = repo_part[:-4]
        pieces = [part for part in repo_part.split("/") if part]
        if len(pieces) != 2:
            return False, "", "", f"Invalid GitHub repository URL: {github_url}"
        return True, pieces[0], pieces[1], ""

    parsed = urlparse(text)
    if parsed.scheme not in {"https", "http"} or parsed.netloc.lower() != "github.com":
        return False, "", "", f"Invalid GitHub repository URL: {github_url}"

    pieces = [part for part in parsed.path.strip("/").split("/") if part]
    if len(pieces) < 2:
        return False, "", "", f"Invalid GitHub repository URL: {github_url}"
    if len(pieces) > 2:
        return (
            False,
            "",
            "",
            "install_skill only accepts a repository root URL. Subpaths like /tree/... or /blob/... are not installable.",
        )

    owner, repo = pieces[0], pieces[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return True, owner, repo, ""


def find_skill_candidates(repo_dir: Path) -> list[Path]:
    root_skill = repo_dir / "SKILL.md"
    if root_skill.exists():
        return [repo_dir]

    candidates: list[Path] = []
    for skill_md in repo_dir.rglob("SKILL.md"):
        try:
            relative = skill_md.relative_to(repo_dir)
        except ValueError:
            continue
        if any(part.startswith(".git") for part in relative.parts):
            continue
        candidates.append(skill_md.parent)

    unique: list[Path] = []
    seen: set[Path] = set()
    for item in sorted(candidates):
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def skill_name_from_dir(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return skill_dir.name
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        return skill_dir.name
    if not content.startswith("---"):
        return skill_dir.name
    try:
        frontmatter_end = content.find("---", 3)
        if frontmatter_end <= 0:
            return skill_dir.name
        import yaml

        metadata = yaml.safe_load(content[3:frontmatter_end]) or {}
        name = str(metadata.get("name", "") or "").strip()
        return name or skill_dir.name
    except Exception:
        return skill_dir.name


async def clone_repo(repo_url: str, dest_dir: Path) -> tuple[bool, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        "--depth",
        "1",
        repo_url,
        str(dest_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return False, "Git clone timed out (120s limit)"

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")
        return False, f"Failed to clone repository: {stderr_text}"
    return True, ""


class SkillInstallerService:
    """Install validated skills into the workspace layout."""

    def __init__(self, layout: WorkspaceLayout):
        self.layout = layout
        self.layout.ensure_directories()

    async def install_from_github(self, github_url: str) -> SkillInstallResult:
        ok, owner, repo, error = parse_github_repo(github_url)
        if not ok:
            return SkillInstallResult(False, error)

        clone_url = f"https://github.com/{owner}/{repo}"
        source_repo_dir = self.layout.skill_sources_dir / f"{owner}__{repo}"
        if source_repo_dir.exists():
            shutil.rmtree(source_repo_dir, ignore_errors=True)
        tmp_clone_dir = self.layout.skill_sources_dir / f".tmp-{owner}__{repo}-{uuid4().hex[:8]}"

        try:
            logger.info(f"Cloning skill source {clone_url} to {tmp_clone_dir}")
            cloned, clone_error = await clone_repo(clone_url, tmp_clone_dir)
            if not cloned:
                shutil.rmtree(tmp_clone_dir, ignore_errors=True)
                return SkillInstallResult(False, clone_error)

            tmp_clone_dir.replace(source_repo_dir)
            candidates = find_skill_candidates(source_repo_dir)
            if not candidates:
                return SkillInstallResult(
                    False,
                    "Repository cloned successfully but does not contain an installable SKILL.md. "
                    "install_skill only installs validated skill directories.",
                )
            if len(candidates) > 1:
                candidate_labels = ", ".join(str(path.relative_to(source_repo_dir)) for path in candidates[:8])
                return SkillInstallResult(
                    False,
                    "Repository contains multiple installable skills and is ambiguous for install_skill. "
                    f"Candidates: {candidate_labels}",
                )

            selected_dir = candidates[0]
            skill_name = skill_name_from_dir(selected_dir)
            install_slug = selected_dir.name if selected_dir != source_repo_dir else repo
            target_dir = self.layout.installed_skills_dir / install_slug
            if target_dir.exists():
                return SkillInstallResult(
                    True,
                    f"Skill '{skill_name}' already installed at {target_dir}",
                    path=str(target_dir),
                    skill_name=skill_name,
                    github_url=clone_url,
                )

            shutil.copytree(selected_dir, target_dir)
            metadata = {
                "github_url": clone_url,
                "owner": owner,
                "repo": repo,
                "source_repo_dir": str(source_repo_dir),
                "source_subdir": "." if selected_dir == source_repo_dir else str(selected_dir.relative_to(source_repo_dir)),
            }
            (target_dir / SKILL_METADATA_FILENAME).write_text(
                json.dumps(metadata, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return SkillInstallResult(
                True,
                f"Successfully installed skill '{skill_name}' from {clone_url}",
                path=str(target_dir),
                skill_name=skill_name,
                github_url=clone_url,
            )
        except Exception as exc:
            logger.error(f"Failed to install skill: {exc}")
            shutil.rmtree(tmp_clone_dir, ignore_errors=True)
            return SkillInstallResult(False, str(exc))
