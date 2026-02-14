#!/usr/bin/env python3
"""
Carrabis Blog Archive — Streamlit App
======================================
Usage (local):
    pip install streamlit beautifulsoup4
    python -m streamlit run app.py

Deploy to Streamlit Community Cloud:
    1. Push to GitHub (app.py, requirements.txt, and carrabis_archive/carrabis_blogs.db)
    2. Go to share.streamlit.io, connect repo, deploy
"""

import sqlite3
import re
import html as html_lib
from pathlib import Path

import streamlit as st
from bs4 import BeautifulSoup, Comment

# ============================================================================
# CONFIG
# ============================================================================

DB_PATH = Path("carrabis_archive") / "carrabis_blogs_deploy.db"

st.set_page_config(
    page_title="Carrabis Blog Archive",
    page_icon="\u26be",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CSS
# ============================================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bitter:wght@400;600;700&family=Source+Sans+3:wght@400;600&display=swap');

    .stApp { background-color: #faf9f6; }

    .archive-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: white; padding: 2rem 2rem; border-radius: 12px; margin-bottom: 1.2rem;
        position: relative; overflow: hidden;
    }
    .archive-header::before {
        content: ''; position: absolute; top: -50%; right: -20%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(255,255,255,0.04) 0%, transparent 70%);
        border-radius: 50%;
    }
    .archive-header h1 {
        font-family: 'Bitter', Georgia, serif; font-size: 2rem; font-weight: 700;
        margin: 0 0 0.2rem 0; letter-spacing: -0.5px;
    }
    .archive-header .sub {
        font-family: 'Source Sans 3', sans-serif; font-size: 0.9rem; color: #a8b4c8; margin: 0;
    }

    .stat-row { display: flex; gap: 10px; margin-bottom: 1.2rem; }
    .stat-card {
        background: white; border: 1px solid #e8e6e1; border-radius: 10px;
        padding: 0.8rem 1.2rem; flex: 1; text-align: center;
    }
    .stat-card .num {
        font-family: 'Bitter', serif; font-size: 1.6rem; font-weight: 700;
        color: #1a1a2e; line-height: 1;
    }
    .stat-card .lbl {
        font-family: 'Source Sans 3', sans-serif; font-size: 0.72rem; color: #888;
        text-transform: uppercase; letter-spacing: 0.7px; margin-top: 3px;
    }

    .post-card {
        background: white; border: 1px solid #e8e6e1; border-radius: 10px;
        padding: 1rem 1.3rem; margin-bottom: 5px;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .post-card:hover { border-color: #c5c0b8; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
    .post-card .title {
        font-family: 'Bitter', serif; font-size: 1rem; font-weight: 600;
        color: #1a1a2e; margin: 0 0 3px 0; line-height: 1.3;
    }
    .post-card .meta {
        font-family: 'Source Sans 3', sans-serif; font-size: 0.78rem;
        color: #999; display: flex; gap: 10px; align-items: center;
    }
    .post-card .snippet {
        font-family: 'Source Sans 3', sans-serif; font-size: 0.82rem;
        color: #777; margin-top: 5px; line-height: 1.4;
    }

    .conf-dot {
        display: inline-block; width: 9px; height: 9px;
        border-radius: 50%; margin-right: 2px; vertical-align: middle;
    }

    .full-post {
        background: white; border: 1px solid #e8e6e1; border-radius: 12px;
        padding: 2.2rem; margin-bottom: 1.5rem;
    }
    .full-post h1 {
        font-family: 'Bitter', serif; font-size: 1.7rem; font-weight: 700;
        color: #1a1a2e; line-height: 1.3; margin-bottom: 0.4rem;
    }
    .full-post .meta {
        font-family: 'Source Sans 3', sans-serif; font-size: 0.82rem; color: #999;
        margin-bottom: 1.2rem; padding-bottom: 0.8rem; border-bottom: 2px solid #f0eeea;
    }
    .full-post .meta a { color: #4a6fa5; text-decoration: none; }
    .full-post .meta a:hover { text-decoration: underline; }
    .full-post .body {
        font-family: 'Bitter', Georgia, serif; font-size: 1.02rem;
        line-height: 1.8; color: #333;
    }
    .full-post .body img { max-width: 100%; height: auto; border-radius: 6px; margin: 10px 0; }
    .full-post .body p { margin-bottom: 1em; }
    .full-post .body blockquote {
        border-left: 3px solid #ddd; padding-left: 1rem; margin: 1em 0; color: #555;
    }

    [data-testid="stSidebar"] { background-color: #f5f4f0; }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown {
        color: #333 !important;
    }
    label, .stSelectbox label, .stTextInput label {
        color: #333 !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HTML SANITIZER
# ============================================================================

ALLOWED_TAGS = {
    'p', 'br', 'b', 'i', 'em', 'strong', 'a', 'img', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'td', 'th', 'hr', 'span', 'div',
    'figure', 'figcaption', 'video', 'source', 'iframe',
}

ALLOWED_ATTRS = {
    'a': {'href', 'target', 'rel'},
    'img': {'src', 'alt', 'width', 'height'},
    'iframe': {'src', 'width', 'height', 'frameborder', 'allowfullscreen'},
    'video': {'src', 'controls', 'width', 'height'},
    'source': {'src', 'type'},
    'td': {'colspan', 'rowspan'},
    'th': {'colspan', 'rowspan'},
}

JUNK_PATTERN = re.compile(
    r'(sidebar|nav|menu|footer|header|comment|social|share|related|'
    r'newsletter|popup|modal|overlay|ad-|advertisement|cookie|'
    r'wm-ipp|wayback|toolbar|donate)', re.IGNORECASE
)


def sanitize_html(raw_html):
    """Strip body_html to just article content. Removes nav, sidebar, scripts, etc."""
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, "html.parser")

    # Nuke script, style, nav, etc.
    for tag in soup.find_all([
        'script', 'style', 'nav', 'header', 'footer', 'noscript',
        'link', 'meta', 'head',
    ]):
        tag.decompose()

    # Remove elements with junk class/id patterns
    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue
        tag_classes = tag.get('class', [])
        if isinstance(tag_classes, list):
            classes = ' '.join(tag_classes)
        else:
            classes = str(tag_classes) if tag_classes else ''
        tag_id = tag.get('id', '') or ''
        if JUNK_PATTERN.search(classes) or JUNK_PATTERN.search(str(tag_id)):
            tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Unwrap disallowed tags (keep children)
    for tag in soup.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()

    # Strip disallowed attributes
    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue
        allowed = ALLOWED_ATTRS.get(tag.name, set())
        for attr in list(tag.attrs):
            if attr not in allowed:
                del tag[attr]

    result = str(soup).strip()
    return result if len(result) > 50 else ""


def clean_body_text(text):
    """
    Strip comments, sidebar tweets, footer junk from body_text.
    Old wordpress-era posts have all of this baked into the text.
    """
    if not text:
        return text

    # Patterns that indicate end of article content
    cut_patterns = [
        r'Follow\s+@\w+\s+Share\s+Tweet',
        r'Share\s+Tweet\s+React\s*\(\d+\)',
        r'Top \d+ Comments',
        r'\d+ comments?\s+Sort by',
        r'Comments will close out',
        r'Thumbs Up\s+Thumbs Down\s+by\s+',
        r'Up:\s*\d+\s*Down:\s*\d+',
        r'Leave a Comment',
        r'Tweets\s+.*?http://t\.co/',
        r'Tour Dates\s+',
        r'Featured Video\s+',
        r'View more Videos',
        r'Â©\s*\d{4}\s*Barstool',
        r'Disclaimer\s*\|\s*Copyright',
        r'Media Kit\s*$',
        r'Barstool Sports\s*\|\s*Disclaimer',
    ]

    for pattern in cut_patterns:
        match = re.search(pattern, text)
        if match:
            # Cut everything from this point
            text = text[:match.start()].rstrip()
            break

    # Also strip "By carrabis posted November 24th, 2014 at 10:00 AM" bylines at the end
    text = re.sub(
        r'\s*By\s+\w+\s+posted\s+\w+\s+\d+.*$',
        '', text, flags=re.IGNORECASE
    ).rstrip()

    # Strip "Home The Store BarstoolTV Cities..." nav text at the start
    nav_match = re.match(
        r'(Home\s+The Store\s+BarstoolTV\s+.*?Barstool Sports\s+All Categories\s+)',
        text, re.IGNORECASE | re.DOTALL
    )
    if nav_match:
        text = text[nav_match.end():].lstrip()

    return text.strip()


def get_display_html(post):
    """Get displayable HTML for a post."""
    body_html = post.get("body_html") or ""
    era = post.get("era") or ""

    # nextjs_v2 body_html is already clean from __NEXT_DATA__
    if era == "nextjs_v2" and body_html:
        return body_html

    # Other eras need sanitizing
    if body_html:
        try:
            cleaned = sanitize_html(body_html)
            if cleaned:
                return cleaned
        except Exception:
            pass

    # Fallback: body_text to paragraphs (with junk stripped)
    body_text = post.get("body_text") or "No content available."
    body_text = clean_body_text(body_text)

    # Try double newlines first, then single
    paragraphs = body_text.split('\n\n')
    if len(paragraphs) <= 1:
        paragraphs = body_text.split('\n')
    return ''.join(f'<p>{html_lib.escape(p.strip())}</p>' for p in paragraphs if p.strip())


# ============================================================================
# DATABASE
# ============================================================================

@st.cache_resource
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=600)
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    carrabis = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE author='Jared Carrabis'"
    ).fetchone()[0]

    # Only valid dates
    row = conn.execute(
        "SELECT MIN(date_published), MAX(date_published) "
        "FROM posts WHERE author='Jared Carrabis' "
        "AND date_published IS NOT NULL "
        "AND date_published >= '2010-01-01' AND date_published <= '2025-12-31'"
    ).fetchone()

    by_conf = {}
    for r in conn.execute(
        "SELECT confidence, COUNT(*) FROM posts WHERE author='Jared Carrabis' GROUP BY confidence"
    ):
        by_conf[r[0] or "none"] = r[1]

    dated = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE author='Jared Carrabis' "
        "AND date_published IS NOT NULL "
        "AND date_published >= '2010-01-01' AND date_published <= '2025-12-31'"
    ).fetchone()[0]

    return {
        "total": total,
        "carrabis": carrabis,
        "min_date": row[0] or "?",
        "max_date": row[1] or "?",
        "by_conf": by_conf,
        "dated": dated,
        "undated": carrabis - dated,
    }


def _fts_escape(query):
    """Quote each word for safe FTS5 matching."""
    if '"' in query:
        return query
    words = query.split()
    return " ".join(f'"{w}"' for w in words if w)


def search_posts(title_query="", body_query="", confidence="all",
                 sort="Newest first", limit=50, offset=0):
    conn = get_db()
    using_fts = False
    conf_vals = []

    # --- Build confidence filter ---
    conf_clause = ""
    if confidence != "all":
        conf_vals = [c.strip() for c in confidence.split(",")]
        conf_clause = f"AND p.confidence IN ({','.join('?' * len(conf_vals))})"

    # --- Build FTS match ---
    fts_parts = []
    if title_query.strip():
        fts_parts.append(f"title:{_fts_escape(title_query.strip())}")
    if body_query.strip():
        fts_parts.append(f"body_text:{_fts_escape(body_query.strip())}")

    fts_match = " AND ".join(fts_parts) if fts_parts else ""
    using_fts = bool(fts_match)

    # --- Relevance sort: join with FTS rank ---
    if sort == "Most relevant" and using_fts:
        params = conf_vals + [fts_match]

        total = conn.execute(f"""
            SELECT COUNT(*) FROM posts p
            JOIN posts_fts fts ON p.id = fts.rowid
            WHERE p.author = 'Jared Carrabis' {conf_clause}
            AND posts_fts MATCH ?
        """, params).fetchone()[0]

        rows = conn.execute(f"""
            SELECT p.id, p.title, p.date_published, p.confidence, p.match_strategy,
                   p.wayback_url, p.original_url, substr(p.body_text, 1, 300) as snippet
            FROM posts p
            JOIN posts_fts fts ON p.id = fts.rowid
            WHERE p.author = 'Jared Carrabis' {conf_clause}
            AND posts_fts MATCH ?
            ORDER BY fts.rank
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        return total, [dict(r) for r in rows]

    # --- Standard sort ---
    sort_map = {
        "Newest first": "p.date_published DESC",
        "Oldest first": "p.date_published ASC",
        "Title A-Z": "p.title ASC",
        "Title Z-A": "p.title DESC",
    }
    order = sort_map.get(sort, "p.date_published DESC")

    if using_fts:
        params = conf_vals + [fts_match]
        total = conn.execute(f"""
            SELECT COUNT(*) FROM posts p
            JOIN posts_fts fts ON p.id = fts.rowid
            WHERE p.author = 'Jared Carrabis' {conf_clause}
            AND posts_fts MATCH ?
        """, params).fetchone()[0]

        rows = conn.execute(f"""
            SELECT p.id, p.title, p.date_published, p.confidence, p.match_strategy,
                   p.wayback_url, p.original_url, substr(p.body_text, 1, 300) as snippet
            FROM posts p
            JOIN posts_fts fts ON p.id = fts.rowid
            WHERE p.author = 'Jared Carrabis' {conf_clause}
            AND posts_fts MATCH ?
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()
    else:
        params = conf_vals
        total = conn.execute(f"""
            SELECT COUNT(*) FROM posts p
            WHERE p.author = 'Jared Carrabis' {conf_clause}
        """, params).fetchone()[0]

        rows = conn.execute(f"""
            SELECT p.id, p.title, p.date_published, p.confidence, p.match_strategy,
                   p.wayback_url, p.original_url, substr(p.body_text, 1, 300) as snippet
            FROM posts p
            WHERE p.author = 'Jared Carrabis' {conf_clause}
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

    return total, [dict(r) for r in rows]


def get_post(post_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, title, author, date_published, body_html, body_text, "
        "wayback_url, original_url, confidence, match_strategy, era "
        "FROM posts WHERE id = ?",
        (post_id,),
    ).fetchone()
    return dict(row) if row else None


# ============================================================================
# UI HELPERS
# ============================================================================

CONF_COLORS = {"high": "#2a9d2a", "medium": "#cc9900", "low": "#cc3333", "none": "#888888"}
CONF_LABELS = {"high": "High", "medium": "Medium", "low": "Low", "none": "None"}


def format_date(date_str):
    if not date_str or date_str < "2010" or date_str > "2025":
        return "No date"
    return date_str


def render_header(stats):
    st.markdown(f"""
    <div class="archive-header">
        <h1>\u26be Carrabis Blog Archive</h1>
        <p class="sub">{stats['carrabis']:,} posts recovered from the Wayback Machine
        &bull; {stats['min_date']} to {stats['max_date']}
        &bull; {stats['undated']:,} undated</p>
    </div>
    """, unsafe_allow_html=True)


def render_stats(stats):
    conf = stats["by_conf"]
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card">
            <div class="num">{stats['carrabis']:,}</div>
            <div class="lbl">Carrabis Posts</div>
        </div>
        <div class="stat-card">
            <div class="num">{conf.get('high', 0):,}</div>
            <div class="lbl">High Confidence</div>
        </div>
        <div class="stat-card">
            <div class="num">{conf.get('medium', 0):,}</div>
            <div class="lbl">Medium Confidence</div>
        </div>
        <div class="stat-card">
            <div class="num">{stats['dated']:,}</div>
            <div class="lbl">With Dates</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_post_card(post):
    title = html_lib.escape(post["title"] or "Untitled")
    date = format_date(post.get("date_published"))
    conf = post["confidence"] or "none"
    color = CONF_COLORS.get(conf, "#888")
    label = CONF_LABELS.get(conf, "?")
    snippet = html_lib.escape((post.get("snippet") or "")[:200])

    st.markdown(f"""
    <div class="post-card">
        <div class="title">{title}</div>
        <div class="meta">
            <span>{date}</span>
            <span><span class="conf-dot" style="background:{color};"></span>{label}</span>
        </div>
        {f'<div class="snippet">{snippet}...</div>' if snippet else ''}
    </div>
    """, unsafe_allow_html=True)


def render_full_post(post):
    title = html_lib.escape(post["title"] or "Untitled")
    date = format_date(post.get("date_published"))
    conf = post["confidence"] or "none"
    color = CONF_COLORS.get(conf, "#888")
    label = CONF_LABELS.get(conf, "?")
    wayback = post.get("wayback_url", "")
    original = post.get("original_url", "")
    era = post.get("era", "unknown")
    body = get_display_html(post)

    st.markdown(f"""
    <div class="full-post">
        <h1>{title}</h1>
        <div class="meta">
            Jared Carrabis &bull; {date} &bull;
            <span class="conf-dot" style="background:{color};"></span>{label} confidence &bull;
            Era: {era}
            <br>
            <a href="{wayback}" target="_blank">View on Wayback Machine</a>
            &nbsp;|&nbsp;
            <a href="{original}" target="_blank">Original URL</a>
        </div>
        <div class="body">{body}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# MAIN
# ============================================================================

def main():
    if not DB_PATH.exists():
        st.error(f"Database not found at `{DB_PATH}`. Run the scraper first.")
        return

    stats = get_stats()

    if "viewing_post" not in st.session_state:
        st.session_state.viewing_post = None
    if "page" not in st.session_state:
        st.session_state.page = 0

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Search")

        title_search = st.text_input(
            "Title search",
            placeholder="e.g. red sox mookie",
            help="Search post titles. Use quotes for exact phrases.",
        )
        body_search = st.text_input(
            "Body search",
            placeholder="e.g. spring training",
            help="Search post body text. Use quotes for exact phrases.",
        )

        st.markdown("### Filters")

        has_search = bool(title_search.strip() or body_search.strip())
        sort_options = ["Newest first", "Oldest first", "Title A-Z", "Title Z-A"]
        if has_search:
            sort_options.insert(0, "Most relevant")

        sort_order = st.selectbox("Sort by", sort_options)

        confidence_filter = st.selectbox(
            "Confidence",
            ["all", "high", "high,medium", "medium", "low", "none"],
            format_func=lambda x: {
                "all": "All", "high": "High only", "high,medium": "High + Medium",
                "medium": "Medium only", "low": "Low only", "none": "None only",
            }.get(x, x),
        )

        per_page = st.select_slider("Posts per page", options=[25, 50, 100], value=50)

        st.markdown("---")
        st.markdown(
            f"**{stats['carrabis']:,}** Carrabis posts\n\n"
            f"**{stats['dated']:,}** dated, **{stats['undated']:,}** undated\n\n"
            f"Range: {stats['min_date']} to {stats['max_date']}"
        )

    # --- Single post view ---
    if st.session_state.viewing_post is not None:
        render_header(stats)
        if st.button("\u2190 Back to results", type="primary"):
            st.session_state.viewing_post = None
            st.rerun()
        post = get_post(st.session_state.viewing_post)
        if post:
            render_full_post(post)
        else:
            st.error("Post not found.")
        return

    # --- List view ---
    render_header(stats)
    render_stats(stats)

    # Reset page on filter change
    search_key = f"{title_search}|{body_search}|{confidence_filter}|{sort_order}"
    if "last_search_key" not in st.session_state:
        st.session_state.last_search_key = search_key
    if st.session_state.last_search_key != search_key:
        st.session_state.page = 0
        st.session_state.last_search_key = search_key

    page = st.session_state.page
    offset = page * per_page

    total, posts = search_posts(
        title_query=title_search,
        body_query=body_search,
        confidence=confidence_filter,
        sort=sort_order,
        limit=per_page,
        offset=offset,
    )

    total_pages = max(1, (total + per_page - 1) // per_page)

    # Results header
    search_desc = []
    if title_search.strip():
        search_desc.append(f'title: "{html_lib.escape(title_search)}"')
    if body_search.strip():
        search_desc.append(f'body: "{html_lib.escape(body_search)}"')

    if search_desc:
        st.markdown(
            f"**{total:,}** results for {', '.join(search_desc)} "
            f"&mdash; Page {page + 1} of {total_pages}",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"**{total:,}** posts &mdash; Page {page + 1} of {total_pages}",
            unsafe_allow_html=True,
        )

    if not posts:
        st.info("No posts match your filters.")
        return

    for post in posts:
        col1, col2 = st.columns([10, 1])
        with col1:
            render_post_card(post)
        with col2:
            st.write("")
            if st.button("Read", key=f"read_{post['id']}"):
                st.session_state.viewing_post = post["id"]
                st.rerun()

    # Pagination
    st.markdown("---")
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if page > 0 and st.button("\u2190 Previous"):
            st.session_state.page = page - 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<div style='text-align:center;color:#888;padding-top:8px;'>"
            f"Page {page + 1} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if page < total_pages - 1 and st.button("Next \u2192"):
            st.session_state.page = page + 1
            st.rerun()


if __name__ == "__main__":
    main()
