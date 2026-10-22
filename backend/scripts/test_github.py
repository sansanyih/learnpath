"""Quick GitHub API probe (metadata, tree, README, ranking)."""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repo.filter import compact_file_list, pick_readme, rank_files  # noqa: E402
from app.repo.github import GitHubClient, parse_repo_url  # noqa: E402

URL = "https://github.com/bnufw/lear_by_ai"


async def main() -> None:
    parsed = parse_repo_url(URL)
    async with GitHubClient() as gh:
        meta = await gh.repo(parsed.owner, parsed.repo)
        print(f"repo={meta['full_name']} branch={meta['default_branch']} lang={meta.get('language')}")
        tree = await gh.tree(parsed.owner, parsed.repo, meta["default_branch"])
        blobs = [item for item in tree["tree"] if item["type"] == "blob"]
        print(f"blobs={len(blobs)} truncated={tree.get('truncated')}")
        paths = [item["path"] for item in blobs]
        readme = pick_readme(paths)
        readme_text = ""
        if readme:
            readme_text = await gh.content(parsed.owner, parsed.repo, readme, meta["default_branch"])
        ranked = rank_files(blobs, readme_text)
        print(f"readme={readme} ranked={len(ranked)}")
        print(compact_file_list(ranked[:10]))


if __name__ == "__main__":
    asyncio.run(main())
