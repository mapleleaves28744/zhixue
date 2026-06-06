from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.course_kb_common import DEFAULT_SOURCE_ROOT, ensure_phase1_dirs, write_yaml


def default_sources() -> list[dict[str, Any]]:
    now = datetime.now(UTC).date().isoformat()
    return [
        {
            "source_id": "self-curated-draft",
            "name": "当前自有数据结构知识库草稿",
            "url": "data/数据结构知识库",
            "institution": "智学工坊",
            "source_type": "self_curated_draft",
            "license": "self-curated",
            "license_url": "",
            "import_status": "approved_importable",
            "review_status": "approved",
            "reviewer": "project-owner",
            "approved_at": now,
            "risk_level": "low",
            "quality_score": 72,
            "coverage": ["course_outline", "wiki_seed", "chunks", "graph", "quiz", "code_case"],
            "local_path": "normalized/self_curated",
            "download_urls": [],
            "notes": "作为冷启动草稿使用，不能冒充外部教材；必须被权威来源补强和质量评估。",
        },
        {
            "source_id": "open-data-structures",
            "name": "Open Data Structures (in pseudocode)",
            "url": "https://opendatastructures.org/ods-python/",
            "institution": "Pat Morin / Open Data Structures",
            "source_type": "open_textbook",
            "license": "CC BY",
            "license_url": "https://opendatastructures.org/ods-python/About_this_document.html",
            "import_status": "approved_importable",
            "review_status": "approved",
            "reviewer": "project-owner",
            "approved_at": now,
            "risk_level": "low",
            "quality_score": 95,
            "coverage": ["array_list", "linked_list", "hash_table", "heap", "sorting", "graph"],
            "local_path": "raw/open-data-structures",
            "download_urls": [
                {
                    "url": "https://opendatastructures.org/ods-python/2_Array_Based_Lists.html",
                    "chapter_id": "ch03",
                    "title": "Array-Based Lists",
                },
                {
                    "url": "https://opendatastructures.org/ods-python/3_Linked_Lists.html",
                    "chapter_id": "ch04",
                    "title": "Linked Lists",
                },
                {
                    "url": "https://opendatastructures.org/ods-python/5_Hash_Tables.html",
                    "chapter_id": "ch11",
                    "title": "Hash Tables",
                },
                {
                    "url": "https://opendatastructures.org/ods-python/12_Graphs.html",
                    "chapter_id": "ch12",
                    "title": "Graphs",
                },
            ],
            "notes": "CC BY 可导入，适合补强基础结构和图章节 grounding。",
        },
        {
            "source_id": "mit-ocw-6006",
            "name": "MIT OCW 6.006 Introduction to Algorithms",
            "url": "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/",
            "institution": "MIT OpenCourseWare",
            "source_type": "university_course",
            "license": "CC BY-NC-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "import_status": "approved_importable",
            "review_status": "approved",
            "reviewer": "project-owner",
            "approved_at": now,
            "risk_level": "medium",
            "quality_score": 94,
            "coverage": ["complexity", "hashing", "binary_search_tree", "graph", "shortest_path"],
            "local_path": "raw/mit-ocw-6006",
            "download_urls": [
                {
                    "url": "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/",
                    "chapter_id": "ch02",
                    "title": "MIT 6.006 Course Overview",
                }
            ],
            "notes": "用户已选择非商导入；导入内容必须保留 CC BY-NC-SA 约束。",
        },
        {
            "source_id": "runestone-pythonds",
            "name": "Problem Solving with Algorithms and Data Structures using Python",
            "url": "https://runestone.academy/ns/books/published/pythonds/index.html",
            "institution": "Runestone Academy / Luther College",
            "source_type": "open_textbook",
            "license": "CC BY-NC-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "import_status": "approved_importable",
            "review_status": "approved",
            "reviewer": "project-owner",
            "approved_at": now,
            "risk_level": "medium",
            "quality_score": 93,
            "coverage": ["python", "stack", "queue", "recursion", "tree", "graph", "sorting"],
            "local_path": "raw/runestone-pythonds",
            "download_urls": [
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/README.rst",
                    "chapter_id": "ch03",
                    "title": "PythonDS README and License",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/BasicDS/WhatisaStack.rst",
                    "chapter_id": "ch05",
                    "title": "What is a Stack",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/BasicDS/ImplementingaStackinPython.rst",
                    "chapter_id": "ch05",
                    "title": "Implementing a Stack in Python",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/BasicDS/WhatIsaQueue.rst",
                    "chapter_id": "ch05",
                    "title": "What is a Queue",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/BasicDS/ImplementingaQueueinPython.rst",
                    "chapter_id": "ch05",
                    "title": "Implementing a Queue in Python",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/BasicDS/ImplementinganUnorderedListLinkedLists.rst",
                    "chapter_id": "ch04",
                    "title": "Implementing an Unordered List with Linked Lists",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/SortSearch/Hashing.rst",
                    "chapter_id": "ch11",
                    "title": "Hashing",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/Trees/BinaryHeapImplementation.rst",
                    "chapter_id": "ch09",
                    "title": "Binary Heap Implementation",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/Graphs/AnAdjacencyList.rst",
                    "chapter_id": "ch12",
                    "title": "An Adjacency List",
                },
                {
                    "url": "https://raw.githubusercontent.com/RunestoneInteractive/pythonds/master/_sources/Graphs/ImplementingBreadthFirstSearch.rst",
                    "chapter_id": "ch12",
                    "title": "Implementing Breadth First Search",
                }
            ],
            "notes": "适合中文高校+Python 风格的代码解释 grounding；下载使用 GitHub raw，非商业约束必须显式展示。",
        },
        {
            "source_id": "opendsa",
            "name": "OpenDSA",
            "url": "https://opendsa.org/",
            "institution": "OpenDSA Project",
            "source_type": "interactive_textbook",
            "license": "MIT License",
            "license_url": "https://opendsa.org/home/license",
            "import_status": "approved_importable",
            "review_status": "approved",
            "reviewer": "project-owner",
            "approved_at": now,
            "risk_level": "low",
            "quality_score": 88,
            "coverage": ["visualization", "interactive_exercise", "data_structure"],
            "local_path": "raw/opendsa",
            "download_urls": [
                {
                    "url": "http://opendsa.org/home/license",
                    "chapter_id": "ch19",
                    "title": "OpenDSA License",
                },
                {
                    "url": "http://opendsa.org/OpenDSA/Books/Everything/html/StackArray.html",
                    "chapter_id": "ch05",
                    "title": "OpenDSA Array-Based Stack",
                },
                {
                    "url": "http://opendsa.org/OpenDSA/Books/Everything/html/StackLinked.html",
                    "chapter_id": "ch05",
                    "title": "OpenDSA Linked Stack",
                },
                {
                    "url": "http://opendsa.org/OpenDSA/Books/Catalog/html/HashIntro.html",
                    "chapter_id": "ch11",
                    "title": "OpenDSA Hashing Introduction",
                },
                {
                    "url": "http://opendsa.org/OpenDSA/Books/Catalog/html/GraphIntro.html",
                    "chapter_id": "ch12",
                    "title": "OpenDSA Graph Representations",
                },
                {
                    "url": "http://opendsa.org/OpenDSA/Books/Catalog/html/GraphImpl.html",
                    "chapter_id": "ch12",
                    "title": "OpenDSA Graph Implementations",
                }
            ],
            "notes": "Phase 1 主要用于可视化/交互资料参考，Phase 7 可继续深化。",
        },
        {
            "source_id": "princeton-algs4",
            "name": "Algorithms, 4th Edition Booksite",
            "url": "https://algs4.cs.princeton.edu/",
            "institution": "Princeton / Robert Sedgewick and Kevin Wayne",
            "source_type": "course_booksite",
            "license": "link-only",
            "license_url": "https://algs4.cs.princeton.edu/code/",
            "import_status": "approved_link_only",
            "review_status": "approved",
            "reviewer": "project-owner",
            "approved_at": now,
            "risk_level": "medium",
            "quality_score": 92,
            "coverage": ["sorting", "searching", "graph", "string"],
            "local_path": "",
            "download_urls": [],
            "notes": "只保留链接和章节映射，不复制全文进入 raw/normalized。",
        },
    ]


def build_manifest() -> dict[str, Any]:
    return {
        "version": "1.0",
        "updated_at": datetime.now(UTC).isoformat(),
        "policy": {
            "source_strategy": "noncommercial_import_allowed",
            "importable_requires": {
                "import_status": "approved_importable",
                "review_status": "approved",
            },
            "link_only_rule": "approved_link_only 只保留链接和映射，不下载全文。",
        },
        "sources": default_sources(),
    }


def write_manifest(source_root: Path = DEFAULT_SOURCE_ROOT) -> Path:
    ensure_phase1_dirs(source_root)
    path = source_root / "sources_manifest.yml"
    write_yaml(path, build_manifest())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover authoritative data-structure course sources.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--dry-run", action="store_true", help="Print source IDs without writing files.")
    args = parser.parse_args()

    manifest = build_manifest()
    if args.dry_run:
        for source in manifest["sources"]:
            print(
                f"{source['source_id']}: {source['import_status']} / "
                f"{source['review_status']} / {source['license']}"
            )
        return

    path = write_manifest(args.source_root)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
