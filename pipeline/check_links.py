"""Check that every cited source URL still resolves.

    python3 -m pipeline.check_links

This is the one part of the toolchain that needs the network, so it is NOT part
of the offline `build` gate — run it on a schedule (see .github/workflows/links.yml)
or by hand. Citations rot: pages get removed, renamed, or moved to another site
(seen already with NHS pages), and a knowledge base built to last a decade has to
notice. Dead or unreachable links fail the check; redirects are reported as
warnings (the citation still works but the URL should probably be updated).
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .loader import load_corpus

REPO_ROOT = Path(__file__).resolve().parent.parent
_UA = "SoftlyKnowledge-linkcheck/1 (+https://softly.app)"


def collect_urls(corpus) -> dict:
    """Map each distinct source URL -> sorted list of atom ids citing it
    (published atoms only — those are what ship)."""
    urls: dict = {}
    for atom in corpus.atoms:
        if atom.status != "published":
            continue
        for src in atom.frontmatter.get("sources") or []:
            urls.setdefault(src["url"], set()).add(atom.id)
    return {u: sorted(ids) for u, ids in sorted(urls.items())}


def _norm(u: str) -> str:
    return u.split("#", 1)[0].rstrip("/").replace("http://", "https://")


def _check_one(url: str, timeout: float):
    """Return (status, detail) where status is 'ok' | 'redirect' | 'dead'."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method,
                                     headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                final = r.geturl()
                if _norm(final) != _norm(url):
                    return ("redirect", final)
                return ("ok", r.status)
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 406, 501):
                continue  # server dislikes HEAD — retry with GET
            return ("dead", f"HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if method == "HEAD":
                continue  # retry with GET before giving up
            return ("dead", f"unreachable: {getattr(e, 'reason', e)}")
    return ("dead", "unreachable")


def check_all(urls: dict, timeout: float, workers: int):
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_check_one, u, timeout): u for u in urls}
        for fut in futs:
            u = futs[fut]
            results[u] = fut.result()
    return results


def _parse_args(argv):
    p = argparse.ArgumentParser(prog="pipeline.check_links",
                                description="Verify cited source URLs resolve.")
    p.add_argument("--content", type=Path, default=REPO_ROOT / "content" / "en")
    p.add_argument("--categories", type=Path,
                   default=REPO_ROOT / "categories" / "categories.yaml")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--strict", action="store_true",
                   help="treat redirects as failures too")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    corpus = load_corpus(args.content, args.categories)
    urls = collect_urls(corpus)
    print(f"Checking {len(urls)} source URL(s)…")
    results = check_all(urls, args.timeout, args.workers)

    dead, redirects, ok = [], [], 0
    for url, (status, detail) in sorted(results.items()):
        if status == "ok":
            ok += 1
        elif status == "redirect":
            redirects.append((url, detail))
        else:
            dead.append((url, detail))

    for url, detail in redirects:
        print(f"  ↪ REDIRECT {url}\n      → {detail}  (cited by: {', '.join(urls[url])})")
    for url, detail in dead:
        print(f"  ✗ DEAD     {url}  [{detail}]\n      cited by: {', '.join(urls[url])}",
              file=sys.stderr)

    print(f"\n{ok} ok, {len(redirects)} redirect(s), {len(dead)} dead.")
    failed = bool(dead) or (args.strict and bool(redirects))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
