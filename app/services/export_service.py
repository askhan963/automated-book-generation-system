from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.models import BookPhase, StageStatus
from app.services import db_service

def compile_book_pdf(book_id: UUID) -> bytes:
    """Generate PDF using WeasyPrint with one chapter per page."""
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.get("final_review_notes_status") != StageStatus.NO_NOTES_NEEDED.value:
        raise HTTPException(status_code=403, detail="Final review not completed")

    chapters = db_service.get_chapters_for_book(book_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters found")

    html_template = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>{book['title']}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Merriweather+Sans:wght@300;400;700&display=swap');
        body {{
            font-family: 'Merriweather', Georgia, serif;
            line-height: 1.6;
            color: #2c3e50;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: white;
        }}
        h1 {{
            color: #1e3a5f;
            font-size: 2.5em;
            margin-bottom: 0.5em;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2c3e50;
            font-size: 1.8em;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}
        h3 {{
            color: #34495e;
            font-size: 1.4em;
            margin-top: 1em;
            margin-bottom: 0.3em;
            opacity: 0.9;
        }}
        p {{
            margin-bottom: 1em;
            text-align: justify;
            hyphens: auto;
        }}
        .chapter {{
            page-break-before: always;
            margin-top: 2em;
        }}
        .chapter:first-child {{
            page-break-before: avoid;
        }}
        .summary {{
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 1em 0;
            font-style: italic;
            color: #5a6c7d;
        }}
        .metadata {{
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 2em;
        }}
        @media print {{
            body {{ margin: 1in; }}
            .chapter {{ page-break-before: always; }}
        }}
    </style>
</head>
<body>
    <div class="metadata">
        <h1>{book['title']}</h1>
        <p>Generated on {book['created_at'].strftime('%B %d, %Y')}</p>
    </div>
"""
    for chapter in chapters:
        summary_html = f"""
    <div class=\"summary\">
        <h3>Summary</h3>
        <p>{chapter.get('summary') or 'No summary available'}</p>
    </div>
""" if chapter.get('summary') else ""
        chapter_html = f"""
    <div class=\"chapter\">
        <h2>Chapter {chapter['chapter_number']}: {chapter['title']}</h2>
        {summary_html}
        <p>{chapter.get('content') or 'Chapter content not available yet.'}</p>
    </div>
"""
        html_template += chapter_html
    html_template += """
</body>
</html>
"""
    try:
        from weasyprint import HTML
        pdf = HTML(string=html_template).write_pdf()
        return pdf
    except ImportError:
        raise HTTPException(status_code=501, detail="WeasyPrint not installed")

def compile_book_epub(book_id: UUID) -> bytes:
    """Generate EPUB using ebook‑lib."""
    try:
        from ebooklib import epub
    except ImportError:
        raise HTTPException(status_code=501, detail="ebook‑lib not installed")
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db_service.get_chapters_for_book(book_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters found")
    epub_book = epub.EpubBook()
    epub_book.set_title(book['title'])
    epub_book.set_language('en')
    epub_book.add_author('Automated Book Generation System')
    for i, chapter in enumerate(chapters, 1):
        chapter_id = f'chap{i}'
        chapter_title = f"Chapter {chapter['chapter_number']}: {chapter['title']}"
        content_html = f"<h1>{chapter_title}</h1>"
        if chapter.get('summary'):
            content_html += f"<div class='summary'><h3>Summary</h3><p>{chapter['summary']}</p></div>"
        content_html += f"<p>{chapter.get('content') or ''}</p>"
        epub_chapter = epub.EpubHtml(title=chapter_title, file_name=f'{chapter_id}.xhtml', lang='en')
        epub_chapter.content = content_html
        epub_book.add_item(epub_chapter)
        epub_book.spine.append(epub_chapter)
        epub_book.toc.append(epub_chapter)
    epub_book.add_item(epub.EpubNcx())
    epub_book.add_item(epub.EpubNav())
    import io
    buf = io.BytesIO()
    epub.write_epub(buf, epub_book)
    return buf.getvalue()

def compile_book_markdown(book_id: UUID) -> str:
    """Export as Markdown."""
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db_service.get_chapters_for_book(book_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters found")
    lines = [f"# {book['title']}\n\n"]
    lines.append(f"*Generated on {book['created_at'].strftime('%Y-%m-%d')}*\n\n")
    for chapter in chapters:
        lines.append(f"## Chapter {chapter['chapter_number']}: {chapter['title']}\n\n")
        if chapter.get('summary'):
            lines.append(f"**Summary:** {chapter['summary']}\n\n")
        lines.append(f"{chapter.get('content') or 'Chapter content not available yet.'}\n\n---\n\n")
    return ''.join(lines).rstrip() + "\n"

def compile_book_html(book_id: UUID) -> str:
    """Export as HTML."""
    book = db_service.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db_service.get_chapters_for_book(book_id)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters found")
    chapter_blocks = []
    for chapter in chapters:
        summary = f"<div class='summary'><h3>Summary</h3><p>{chapter.get('summary')}</p></div>" if chapter.get('summary') else ''
        chapter_blocks.append(f"<div class='chapter'><h2>Chapter {chapter['chapter_number']}: {chapter['title']}</h2>{summary}<p>{chapter.get('content') or ''}</p></div>")
    html = f"""
<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <title>{book['title']}</title>
    <style>
        body {{font-family: 'Merriweather', Georgia, serif; line-height: 1.6; max-width:800px; margin:auto; padding:20px;}}
        h1 {{color:#1e3a5f;}}
        h2 {{color:#2c3e50;}}
        .summary {{background:#f8f9fa; border-left:4px solid #3498db; padding:15px; margin:1em 0;}}
    </style>
</head>
<body>
    <h1>{book['title']}</h1>
    {'\n'.join(chapter_blocks)}
</body>
</html>
"""
    return html

def save_export_file(book_id: UUID, file_type: str, content: Any) -> None:
    """Save export content to the static exports directory."""
    import os, hashlib
    export_dir = os.path.abspath('exports')
    os.makedirs(export_dir, exist_ok=True)
    filename = f"{str(book_id)[:8]}.{file_type}"
    path = os.path.join(export_dir, filename)
    mode = 'wb' if isinstance(content, (bytes, bytearray)) else 'w'
    with open(path, mode) as f:
        f.write(content if 'b' in mode else str(content))
    return f"/exports/{filename}"