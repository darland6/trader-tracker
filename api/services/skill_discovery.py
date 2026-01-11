"""Skill Discovery Service - Find and install skills from Anthropic's skills repo.

This service allows the agent to dynamically discover, install, and use skills
from https://github.com/anthropics/skills based on the current task context.
"""

import httpx
import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

# Anthropic skills repo base URL
SKILLS_REPO_RAW = "https://raw.githubusercontent.com/anthropics/skills/main/skills"
SKILLS_REPO_API = "https://api.github.com/repos/anthropics/skills/contents/skills"

# Local skills directory
LOCAL_SKILLS_DIR = Path.home() / ".claude" / "skills"

# Cache for skill metadata
SKILL_CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "skill_cache.json"


@dataclass
class SkillMetadata:
    """Metadata for a skill."""
    name: str
    description: str
    source: str = "anthropic"  # "anthropic" | "local" | "custom"
    category: str = "general"
    installed: bool = False
    last_updated: Optional[str] = None
    keywords: list = field(default_factory=list)


# Known skills from Anthropic repo with categories and keywords for matching
ANTHROPIC_SKILLS = {
    "frontend-design": SkillMetadata(
        name="Frontend Design",
        description="Create distinctive, production-grade web interfaces that reject generic AI aesthetics",
        category="design",
        keywords=["frontend", "ui", "web", "html", "css", "design", "interface", "styling", "react", "vue"]
    ),
    "web-artifacts-builder": SkillMetadata(
        name="Web Artifacts Builder",
        description="Build interactive web artifacts and single-file HTML applications",
        category="web",
        keywords=["web", "html", "artifact", "interactive", "single-file", "app"]
    ),
    "webapp-testing": SkillMetadata(
        name="WebApp Testing",
        description="Test web applications with automated browser testing",
        category="testing",
        keywords=["test", "testing", "browser", "e2e", "automation", "qa", "selenium", "playwright"]
    ),
    "mcp-builder": SkillMetadata(
        name="MCP Builder",
        description="Build Model Context Protocol servers and tools",
        category="development",
        keywords=["mcp", "protocol", "server", "tool", "integration", "api"]
    ),
    "skill-creator": SkillMetadata(
        name="Skill Creator",
        description="Create new skills for Claude Code following best practices",
        category="meta",
        keywords=["skill", "create", "build", "claude", "agent", "workflow"]
    ),
    "pdf": SkillMetadata(
        name="PDF",
        description="Work with PDF documents - read, analyze, extract",
        category="document",
        keywords=["pdf", "document", "read", "extract", "analyze"]
    ),
    "docx": SkillMetadata(
        name="DOCX",
        description="Work with Word documents",
        category="document",
        keywords=["docx", "word", "document", "microsoft", "office"]
    ),
    "pptx": SkillMetadata(
        name="PPTX",
        description="Work with PowerPoint presentations",
        category="document",
        keywords=["pptx", "powerpoint", "presentation", "slides", "microsoft"]
    ),
    "xlsx": SkillMetadata(
        name="XLSX",
        description="Work with Excel spreadsheets",
        category="document",
        keywords=["xlsx", "excel", "spreadsheet", "data", "microsoft"]
    ),
    "canvas-design": SkillMetadata(
        name="Canvas Design",
        description="Create visual designs using HTML canvas",
        category="design",
        keywords=["canvas", "design", "graphics", "drawing", "visual"]
    ),
    "theme-factory": SkillMetadata(
        name="Theme Factory",
        description="Generate consistent design themes and color palettes",
        category="design",
        keywords=["theme", "color", "palette", "design", "branding", "style"]
    ),
    "algorithmic-art": SkillMetadata(
        name="Algorithmic Art",
        description="Create generative and algorithmic artwork",
        category="creative",
        keywords=["art", "generative", "algorithmic", "creative", "visual"]
    ),
    "doc-coauthoring": SkillMetadata(
        name="Doc Co-authoring",
        description="Collaboratively write and edit documents",
        category="writing",
        keywords=["writing", "document", "collaborate", "edit", "author"]
    ),
    "brand-guidelines": SkillMetadata(
        name="Brand Guidelines",
        description="Create and maintain brand guidelines",
        category="design",
        keywords=["brand", "guidelines", "identity", "style", "logo"]
    ),
    "internal-comms": SkillMetadata(
        name="Internal Comms",
        description="Create internal communications and announcements",
        category="communication",
        keywords=["communication", "internal", "announcement", "email", "memo"]
    ),
    "slack-gif-creator": SkillMetadata(
        name="Slack GIF Creator",
        description="Create custom GIFs for Slack",
        category="communication",
        keywords=["slack", "gif", "animation", "emoji", "communication"]
    ),
}


def get_skill_cache() -> dict:
    """Load skill cache from disk."""
    if SKILL_CACHE_FILE.exists():
        try:
            return json.loads(SKILL_CACHE_FILE.read_text())
        except:
            pass
    return {"skills": {}, "last_refresh": None}


def save_skill_cache(cache: dict) -> None:
    """Save skill cache to disk."""
    SKILL_CACHE_FILE.parent.mkdir(exist_ok=True)
    cache["last_updated"] = datetime.now().isoformat()
    SKILL_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def list_available_skills() -> list[dict]:
    """List all available skills from Anthropic repo and local skills."""
    skills = []

    # Add Anthropic skills
    for skill_id, meta in ANTHROPIC_SKILLS.items():
        # Check if installed locally
        local_path = LOCAL_SKILLS_DIR / skill_id / "SKILL.md"
        installed = local_path.exists()

        skills.append({
            "id": skill_id,
            "name": meta.name,
            "description": meta.description,
            "category": meta.category,
            "source": "anthropic",
            "installed": installed,
            "keywords": meta.keywords
        })

    # Add local-only skills (not from Anthropic)
    if LOCAL_SKILLS_DIR.exists():
        for skill_dir in LOCAL_SKILLS_DIR.iterdir():
            if skill_dir.is_dir():
                skill_id = skill_dir.name
                if skill_id not in ANTHROPIC_SKILLS:
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        content = skill_file.read_text()
                        # Parse frontmatter
                        name = skill_id
                        description = ""
                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                for line in parts[1].strip().split("\n"):
                                    if line.startswith("name:"):
                                        name = line.split(":", 1)[1].strip()
                                    elif line.startswith("description:"):
                                        description = line.split(":", 1)[1].strip()

                        skills.append({
                            "id": skill_id,
                            "name": name,
                            "description": description,
                            "category": "local",
                            "source": "local",
                            "installed": True,
                            "keywords": []
                        })

    return skills


def search_skills(query: str) -> list[dict]:
    """Search for skills matching a query.

    Matches against name, description, and keywords.
    Returns sorted by relevance.
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())

    results = []
    for skill in list_available_skills():
        score = 0

        # Exact match in name
        if query_lower in skill["name"].lower():
            score += 10

        # Exact match in description
        if query_lower in skill["description"].lower():
            score += 5

        # Word matches in keywords
        for keyword in skill.get("keywords", []):
            if keyword.lower() in query_lower:
                score += 8
            elif any(w in keyword.lower() for w in query_words):
                score += 3

        # Word matches in name/description
        for word in query_words:
            if word in skill["name"].lower():
                score += 2
            if word in skill["description"].lower():
                score += 1

        if score > 0:
            results.append({**skill, "relevance_score": score})

    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results


def suggest_skill_for_task(task_description: str) -> Optional[dict]:
    """Suggest the best skill for a given task description.

    Returns the highest-scoring skill if relevance is above threshold.
    """
    results = search_skills(task_description)
    if results and results[0]["relevance_score"] >= 3:
        return results[0]
    return None


async def fetch_skill_content(skill_id: str) -> Optional[str]:
    """Fetch the SKILL.md content from Anthropic's repo."""
    url = f"{SKILLS_REPO_RAW}/{skill_id}/SKILL.md"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
            else:
                print(f"Failed to fetch skill {skill_id}: {response.status_code}")
                return None
    except Exception as e:
        print(f"Error fetching skill {skill_id}: {e}")
        return None


async def install_skill(skill_id: str) -> dict:
    """Install a skill from Anthropic's repo to local ~/.claude/skills/.

    Returns status dict with success boolean and message.
    """
    # Check if already installed
    skill_dir = LOCAL_SKILLS_DIR / skill_id
    skill_file = skill_dir / "SKILL.md"

    if skill_file.exists():
        return {
            "success": True,
            "message": f"Skill '{skill_id}' is already installed",
            "path": str(skill_file),
            "already_installed": True
        }

    # Fetch content
    content = await fetch_skill_content(skill_id)
    if not content:
        return {
            "success": False,
            "message": f"Failed to fetch skill '{skill_id}' from Anthropic repo"
        }

    # Create directory and write file
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content)

        # Update cache
        cache = get_skill_cache()
        cache["skills"][skill_id] = {
            "installed_at": datetime.now().isoformat(),
            "source": "anthropic"
        }
        save_skill_cache(cache)

        return {
            "success": True,
            "message": f"Skill '{skill_id}' installed successfully",
            "path": str(skill_file),
            "already_installed": False
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to install skill '{skill_id}': {e}"
        }


def get_installed_skill_content(skill_id: str) -> Optional[str]:
    """Get the content of an installed skill."""
    skill_file = LOCAL_SKILLS_DIR / skill_id / "SKILL.md"
    if skill_file.exists():
        return skill_file.read_text()
    return None


def uninstall_skill(skill_id: str) -> dict:
    """Remove an installed skill."""
    skill_dir = LOCAL_SKILLS_DIR / skill_id

    if not skill_dir.exists():
        return {
            "success": False,
            "message": f"Skill '{skill_id}' is not installed"
        }

    try:
        import shutil
        shutil.rmtree(skill_dir)

        # Update cache
        cache = get_skill_cache()
        if skill_id in cache.get("skills", {}):
            del cache["skills"][skill_id]
        save_skill_cache(cache)

        return {
            "success": True,
            "message": f"Skill '{skill_id}' uninstalled successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to uninstall skill '{skill_id}': {e}"
        }


# Agent command integration
def get_skill_discovery_commands() -> str:
    """Get the system prompt additions for skill discovery commands.

    These commands can be used by the agent to discover and use skills.
    """
    return """
## Skill Discovery Commands

You have access to a library of skills from Anthropic that can enhance your capabilities.
When you encounter a task that might benefit from a specialized skill, use these commands:

### [SKILL_SEARCH: query]
Search for relevant skills. Example: [SKILL_SEARCH: frontend design]

### [SKILL_INSTALL: skill_id]
Install a skill from Anthropic's repo. Example: [SKILL_INSTALL: frontend-design]

### [SKILL_USE: skill_id]
Use an installed skill for the current task. This will load the skill's instructions.

### Available Skills
Anthropic provides skills for: frontend-design, web-artifacts-builder, webapp-testing,
mcp-builder, pdf, docx, pptx, xlsx, canvas-design, theme-factory, and more.

When to use skills:
- Frontend/UI work: Use "frontend-design" for distinctive web interfaces
- Testing: Use "webapp-testing" for automated browser testing
- Documents: Use "pdf", "docx", "pptx", "xlsx" for document processing
- Building tools: Use "mcp-builder" for MCP server development
"""


# FastAPI router endpoints
def create_skill_router():
    """Create FastAPI router for skill management API."""
    from fastapi import APIRouter, HTTPException

    router = APIRouter(prefix="/api/skills", tags=["skills"])

    @router.get("")
    async def list_skills():
        """List all available skills."""
        return {
            "skills": list_available_skills(),
            "count": len(list_available_skills())
        }

    @router.get("/search")
    async def search(q: str):
        """Search for skills matching a query."""
        results = search_skills(q)
        return {
            "query": q,
            "results": results,
            "count": len(results)
        }

    @router.get("/suggest")
    async def suggest(task: str):
        """Suggest a skill for a task."""
        suggestion = suggest_skill_for_task(task)
        return {
            "task": task,
            "suggestion": suggestion
        }

    @router.post("/install/{skill_id}")
    async def install(skill_id: str):
        """Install a skill from Anthropic's repo."""
        result = await install_skill(skill_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result

    @router.delete("/{skill_id}")
    async def uninstall(skill_id: str):
        """Uninstall a skill."""
        result = uninstall_skill(skill_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result

    @router.get("/{skill_id}")
    async def get_skill(skill_id: str):
        """Get skill details and content if installed."""
        # Check Anthropic skills
        if skill_id in ANTHROPIC_SKILLS:
            meta = ANTHROPIC_SKILLS[skill_id]
            local_content = get_installed_skill_content(skill_id)
            return {
                "id": skill_id,
                "name": meta.name,
                "description": meta.description,
                "category": meta.category,
                "source": "anthropic",
                "installed": local_content is not None,
                "content": local_content,
                "keywords": meta.keywords
            }

        # Check local skills
        local_content = get_installed_skill_content(skill_id)
        if local_content:
            return {
                "id": skill_id,
                "source": "local",
                "installed": True,
                "content": local_content
            }

        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    return router
