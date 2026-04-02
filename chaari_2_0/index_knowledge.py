"""
CHAARI 2.0 — RAPTOR tree indexing script.
Indexes CHAARI source code + architecture PDFs into the hierarchical tree.
Also supports indexing user personal documents into a separate collection.

Usage:
    python index_knowledge.py            # Index CHAARI docs only
    python index_knowledge.py --user     # Index user documents only
    python index_knowledge.py --all      # Index both
"""
import sys, os, time, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.doc_loader import load_and_chunk_file, load_and_chunk_directory
from core.tree_builder import RaptorTreeBuilder
from config.rag import COLLECTION_CHAARI_DOCS, COLLECTION_USER_DOCS, SUPPORTED_EXTENSIONS


def _resolve_user_dirs() -> list[str]:
    """Resolve common user directories for document indexing."""
    dirs = []
    onedrive = os.environ.get("OneDrive", "")
    home = os.path.expanduser("~")

    candidates = ["Documents", "Desktop", "Downloads"]

    for name in candidates:
        if onedrive:
            od_path = os.path.join(onedrive, name)
            if os.path.isdir(od_path):
                dirs.append(od_path)
                continue
        home_path = os.path.join(home, name)
        if os.path.isdir(home_path):
            dirs.append(home_path)

    return dirs


def index_chaari():
    """Index CHAARI source code + architecture PDFs."""
    print("=" * 60)
    print("  CHAARI 2.0 — RAPTOR Tree Indexing (CHAARI Docs)")
    print("=" * 60)

    all_chunks = []
    base = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base)

    asus_dirs = [
        os.path.join(base, "core"),
        os.path.join(base, "config"),
    ]
    main_py = os.path.join(base, "main.py")
    if os.path.exists(main_py):
        chunks = load_and_chunk_file(main_py)
        print(f"  main.py: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    for d in asus_dirs:
        if os.path.exists(d):
            chunks = load_and_chunk_directory(d)
            print(f"  {os.path.basename(d)}/: {len(chunks)} chunks")
            all_chunks.extend(chunks)

    dell_base = os.path.join(project_root, "chaari_dell")
    dell_files = [
        os.path.join(dell_base, "agent.py"),
        os.path.join(dell_base, "config.py"),
    ]
    dell_dirs = [
        os.path.join(dell_base, "executor"),
    ]

    for f in dell_files:
        if os.path.exists(f):
            chunks = load_and_chunk_file(f)
            print(f"  dell/{os.path.basename(f)}: {len(chunks)} chunks")
            all_chunks.extend(chunks)

    for d in dell_dirs:
        if os.path.exists(d):
            chunks = load_and_chunk_directory(d)
            print(f"  dell/{os.path.basename(d)}/: {len(chunks)} chunks")
            all_chunks.extend(chunks)

    # --- 3. Index architecture PDFs ---
    pdf_files = [
        os.path.join(project_root, "CHAARI_2.0_Full_Architecture.pdf"),
        os.path.join(project_root, "chaari 2.0_plan.pdf"),
        os.path.join(project_root, "GUI_dell.pdf"),
        os.path.join(project_root, "Upgrades.pdf"),
    ]

    for f in pdf_files:
        if os.path.exists(f):
            chunks = load_and_chunk_file(f)
            print(f"  PDF {os.path.basename(f)}: {len(chunks)} chunks")
            all_chunks.extend(chunks)
        else:
            print(f"  PDF {os.path.basename(f)}: NOT FOUND, skipping")

    print(f"\n{'=' * 60}")
    print(f"  Total leaf chunks: {len(all_chunks)}")
    print(f"{'=' * 60}")

    if not all_chunks:
        print("ERROR: No chunks found. Check file paths.")
        return

    print("\nBuilding RAPTOR tree (this will make LLM calls for summaries)...\n")
    start = time.time()

    builder = RaptorTreeBuilder(collection_name=COLLECTION_CHAARI_DOCS)
    stats = builder.build_tree(all_chunks)

    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print(f"  RAPTOR Tree Built Successfully! (chaari_docs)")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Levels: {stats.get('levels', 'N/A')}")
    for lvl in range(stats.get('levels', 0)):
        key = f'level_{lvl}_nodes'
        if key in stats:
            print(f"    Level {lvl}: {stats[key]} nodes")
    print(f"  Total nodes: {stats.get('total_nodes', 'N/A')}")
    print(f"{'=' * 60}")


def index_user_docs():
    """Index user's personal documents (Documents, Desktop, Downloads)."""
    print("=" * 60)
    print("  CHAARI 2.0 — RAPTOR Tree Indexing (User Docs)")
    print("=" * 60)

    user_dirs = _resolve_user_dirs()
    if not user_dirs:
        print("  ERROR: No user directories found.")
        return

    all_chunks = []
    exts_str = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    print(f"  Supported extensions: {exts_str}")
    print()

    for udir in user_dirs:
        print(f"  Scanning: {udir}")
        chunks = load_and_chunk_directory(udir, recursive=True)
        print(f"    -> {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"\n{'=' * 60}")
    print(f"  Total user doc chunks: {len(all_chunks)}")
    print(f"{'=' * 60}")

    if not all_chunks:
        print("  No user documents found to index.")
        return

    print("\nBuilding RAPTOR tree for user docs...\n")
    start = time.time()

    builder = RaptorTreeBuilder(collection_name=COLLECTION_USER_DOCS)
    stats = builder.build_tree(all_chunks)

    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print(f"  RAPTOR Tree Built Successfully! (user_docs)")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Levels: {stats.get('levels', 'N/A')}")
    for lvl in range(stats.get('levels', 0)):
        key = f'level_{lvl}_nodes'
        if key in stats:
            print(f"    Level {lvl}: {stats[key]} nodes")
    print(f"  Total nodes: {stats.get('total_nodes', 'N/A')}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="CHAARI 2.0 RAPTOR Tree Indexing")
    parser.add_argument("--user", action="store_true", help="Index user personal documents only")
    parser.add_argument("--all", action="store_true", help="Index both CHAARI docs and user docs")
    args = parser.parse_args()

    if args.all:
        index_chaari()
        print("\n")
        index_user_docs()
    elif args.user:
        index_user_docs()
    else:
        index_chaari()

if __name__ == "__main__":
    main()
