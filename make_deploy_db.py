#!/usr/bin/env python3
"""
Create a minimal database for Streamlit Cloud deployment.
Only Carrabis posts. Keeps body_html for eras with clean HTML
(nextjs_v2, soxspacenews, soxspaceboston).
For other eras, NULLs out body_html (app falls back to body_text).

Usage:
    python make_deploy_db.py
"""

import sqlite3
from pathlib import Path

SRC = Path("carrabis_archive") / "carrabis_blogs.db"
DST = Path("carrabis_archive") / "carrabis_blogs_deploy.db"

# Eras with clean article HTML worth keeping
CLEAN_HTML_ERAS = {"nextjs_v2", "soxspacenews", "soxspaceboston"}


def main():
    src_size = SRC.stat().st_size / (1024 * 1024)
    print(f"Source DB: {src_size:.1f} MB")

    if DST.exists():
        DST.unlink()

    dst = sqlite3.connect(DST)

    dst.execute("""
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            original_url TEXT,
            wayback_url TEXT,
            title TEXT,
            author TEXT,
            date_published TEXT,
            body_text TEXT,
            body_html TEXT,
            confidence TEXT,
            match_strategy TEXT,
            era TEXT,
            source TEXT
        )
    """)

    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row

    rows = src.execute("""
        SELECT id, original_url, wayback_url, title, author,
               date_published, body_text, body_html, confidence,
               match_strategy, era, source
        FROM posts
        WHERE author = 'Jared Carrabis'
    """).fetchall()

    print(f"Copying {len(rows)} Carrabis posts...")

    html_kept = 0
    text_only_count = 0
    source_counts = {}
    batch = []

    for r in rows:
        era = r["era"] or ""
        source = r["source"] or "barstool"

        # Keep body_html for eras with clean article HTML
        if era in CLEAN_HTML_ERAS:
            html = r["body_html"]
            html_kept += 1
        else:
            html = None
            text_only_count += 1

        source_counts[source] = source_counts.get(source, 0) + 1

        batch.append((
            r["id"], r["original_url"], r["wayback_url"], r["title"],
            r["author"], r["date_published"], r["body_text"], html,
            r["confidence"], r["match_strategy"], era, source
        ))

    dst.executemany("INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
    dst.commit()

    print(f"  {html_kept} with body_html ({', '.join(CLEAN_HTML_ERAS)})")
    print(f"  {text_only_count} with body_text only")
    print(f"  By source:")
    for s, c in sorted(source_counts.items()):
        print(f"    {s}: {c}")

    # Build FTS index
    print("Building search index...")
    dst.execute("""
        CREATE VIRTUAL TABLE posts_fts USING fts5(
            title, body_text,
            content='posts',
            content_rowid='id'
        )
    """)
    dst.execute("""
        INSERT INTO posts_fts(rowid, title, body_text)
        SELECT id, title, body_text FROM posts
    """)
    dst.commit()

    dst.execute("CREATE INDEX idx_posts_author ON posts(author)")
    dst.execute("CREATE INDEX idx_posts_confidence ON posts(confidence)")
    dst.execute("CREATE INDEX idx_posts_title ON posts(title)")
    dst.execute("CREATE INDEX idx_posts_source ON posts(source)")
    dst.commit()

    src.close()

    print("Vacuuming...")
    dst.execute("VACUUM")
    dst.close()

    dst_size = DST.stat().st_size / (1024 * 1024)
    print(f"\nDone!")
    print(f"  Original:  {src_size:.1f} MB")
    print(f"  Deploy:    {dst_size:.1f} MB")
    print(f"  Posts:     {len(rows)}")

    if dst_size < 25:
        print(f"\n  Under 25 MB - push directly to GitHub (no LFS needed)!")
    elif dst_size < 100:
        print(f"\n  Under 100 MB - use Git LFS or CLI push")
    else:
        print(f"\n  Over 100 MB - still too big, may need to drop body_html entirely")

    print(f'\nUpdate app.py DB_PATH to:')
    print(f'  DB_PATH = Path("carrabis_archive") / "carrabis_blogs_deploy.db"')


if __name__ == "__main__":
    main()