import asyncio
from pathlib import Path

import markdown

from core.pdf_generator import _generate_pdf_with_playwright


SOURCE_PATH = Path("INTERVIEW_PROJECT_GUIDE.md")
OUTPUT_PATH = Path("INTERVIEW_PROJECT_GUIDE.pdf")


def build_html(markdown_text: str) -> str:
    body = markdown.markdown(markdown_text, extensions=["fenced_code", "tables"])
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        body {{
          font-family: "Aptos", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
          line-height: 1.65;
          color: #1f2937;
          padding: 40px 48px;
          max-width: 900px;
          margin: 0 auto;
        }}
        h1 {{
          font-size: 30px;
          margin-bottom: 8px;
          color: #111827;
          border-bottom: 3px solid #d1d5db;
          padding-bottom: 12px;
        }}
        h2 {{
          font-size: 22px;
          margin-top: 28px;
          color: #0f172a;
          border-left: 5px solid #2563eb;
          padding-left: 12px;
        }}
        h3 {{
          font-size: 17px;
          margin-top: 20px;
          color: #1d4ed8;
        }}
        p, li {{
          font-size: 14px;
        }}
        ul, ol {{
          padding-left: 22px;
        }}
        li {{
          margin: 6px 0;
        }}
        code {{
          background: #f3f4f6;
          border-radius: 4px;
          padding: 2px 6px;
          font-family: "SFMono-Regular", "Menlo", monospace;
          color: #b91c1c;
        }}
        pre {{
          background: #0f172a;
          color: #e5e7eb;
          border-radius: 10px;
          padding: 14px 16px;
          overflow-x: auto;
        }}
        pre code {{
          background: transparent;
          color: inherit;
          padding: 0;
        }}
        strong {{
          color: #111827;
        }}
        blockquote {{
          border-left: 4px solid #93c5fd;
          background: #eff6ff;
          padding: 10px 14px;
          margin: 16px 0;
        }}
      </style>
    </head>
    <body>{body}</body>
    </html>
    """


async def main() -> None:
    markdown_text = SOURCE_PATH.read_text(encoding="utf-8")
    html = build_html(markdown_text)
    await _generate_pdf_with_playwright(html, str(OUTPUT_PATH))
    print(f"Generated PDF: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
