"""
PDF 生成器
使用 Playwright 将 HTML 模板转换为 PDF
支持自适应排版 - 根据内容量动态调整样式参数
"""

import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


# 样式预设：根据内容量选择不同的排版参数
STYLE_PRESETS = {
    "ultra_compact": {
        "font_size": "8pt",
        "line_height": "1.15",
        "section_margin": "4px",
        "entry_margin": "3px",
        "padding": "6mm 8mm",
    },
    "compact": {
        "font_size": "8.5pt",
        "line_height": "1.25",
        "section_margin": "8px",
        "entry_margin": "6px",
        "padding": "8mm 10mm",
    },
    "standard": {
        "font_size": "9pt",
        "line_height": "1.35",
        "section_margin": "12px",
        "entry_margin": "10px",
        "padding": "10mm 12mm",
    },
    "spacious": {
        "font_size": "9.5pt",
        "line_height": "1.45",
        "section_margin": "16px",
        "entry_margin": "14px",
        "padding": "12mm 15mm",
    },
}


def clean_resume_text(text: str) -> str:
    """
    清理简历文本中的格式问题
    修复常见的 LLM 生成错误
    """
    if not text:
        return text

    # ===== 1. LaTeX 格式清理 =====
    # 移除 LaTeX 数学模式 $...$
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    # 转换 LaTeX 箭头为 Unicode 箭头
    text = text.replace(r'\rightarrow', '→')
    text = text.replace(r'\leftarrow', '←')
    text = text.replace(r'\Rightarrow', '⇒')
    text = text.replace(r'\Leftarrow', '⇐')
    text = text.replace(r'\leftrightarrow', '↔')
    # 移除 \hfill 等 LaTeX 命令
    text = re.sub(r'\\hfill\s*', ' ', text)
    text = re.sub(r'\\[a-zA-Z]+\s*', '', text)  # 移除其他 LaTeX 命令

    # ===== 2. 常见拼写错误修复 =====
    # GPT 型号规范化（避免 o/0 混淆）
    text = re.sub(r'GPT-4/4o\b', 'GPT-4o', text)  # GPT-4/4o → GPT-4o（简化写法）
    text = re.sub(r'GPT-4/40\b', 'GPT-4o', text)  # GPT-4/40 → GPT-4o
    text = re.sub(r'GPT-40\b', 'GPT-4o', text)    # GPT-40 → GPT-4o
    text = re.sub(r'GPT4o\b', 'GPT-4o', text)     # GPT4o → GPT-4o
    text = re.sub(r'GPT-4 ?[/,] ?4o\b', 'GPT-4o', text)  # GPT-4, 4o 等变体
    # Generative Al → Generative AI (小写l改成大写I)
    text = re.sub(r'\bGenerative Al\b', 'Generative AI', text)
    text = re.sub(r'\bGenAl\b', 'GenAI', text)  # GenAl → GenAI
    text = re.sub(r'\bAl\b(?=\s+(?:tools|models|systems|applications|platform|engineering|Engineer))', 'AI', text)
    text = re.sub(r'\bAl-', 'AI-', text)  # Al-powered → AI-powered
    # DrissionPage 空格问题
    text = re.sub(r'\bDrission\s+Page\b', 'DrissionPage', text)

    # ===== 3. 符号格式修复 =====
    # 修复百分号后的多余空格
    text = re.sub(r'(\d+%)\s+\+', r'\1+', text)
    # 修复大于/小于符号
    text = re.sub(r'>\s*(\d)', r'> \1', text)
    text = re.sub(r'<\s*(\d)', r'< \1', text)
    # 统一箭头符号（如果有多个连续的 -> 或 -->）
    text = re.sub(r'\s*-+>\s*', ' → ', text)
    text = re.sub(r'\s*<-+\s*', ' ← ', text)

    return text


def _normalize_url(url: str) -> str:
    """确保 URL 有 https:// 前缀"""
    if not url or not isinstance(url, str):
        return url
    url = url.strip()
    if url and not url.startswith(('http://', 'https://')):
        return f'https://{url}'
    return url


def clean_resume_data(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    """递归清理简历数据中的所有文本字段"""
    # URL 字段需要特殊处理，确保有 https:// 前缀
    URL_FIELDS = {'linkedin', 'github', 'portfolio', 'website', 'url'}

    if isinstance(resume_data, dict):
        result = {}
        for k, v in resume_data.items():
            if k.lower() in URL_FIELDS and isinstance(v, str) and v:
                result[k] = _normalize_url(v)
            else:
                result[k] = clean_resume_data(v)
        return result
    elif isinstance(resume_data, list):
        return [clean_resume_data(item) for item in resume_data]
    elif isinstance(resume_data, str):
        return clean_resume_text(resume_data)
    else:
        return resume_data


def _estimate_content_volume(resume_data: Dict[str, Any]) -> str:
    """
    预估内容量，返回推荐的样式预设

    Returns:
        "compact" | "standard" | "spacious"
    """
    score = 0

    # 计算经历条目数和 bullet 数
    experience = resume_data.get("experience", [])
    exp_count = len(experience) if isinstance(experience, list) else 0
    bullet_count = 0
    for exp in (experience if isinstance(experience, list) else []):
        bullets = exp.get("bullets", [])
        bullet_count += len(bullets) if isinstance(bullets, list) else 0

    # 计算项目条目数
    projects = resume_data.get("projects", [])
    proj_count = len(projects) if isinstance(projects, list) else 0

    # 计算技能行数
    skills = resume_data.get("skills", [])
    skill_count = len(skills) if isinstance(skills, list) else 0

    # 计算 summary 长度
    summary = resume_data.get("summary", "")
    summary_len = len(summary) if isinstance(summary, str) else 0

    # 评分逻辑
    score += exp_count * 15
    score += bullet_count * 5
    score += proj_count * 12
    score += skill_count * 3
    score += summary_len // 50

    print(f"[PDF] 内容量评分: {score} (经历:{exp_count}, bullets:{bullet_count}, 项目:{proj_count})")

    # 根据评分选择样式
    if score > 120:
        return "compact"
    elif score > 60:
        return "standard"
    else:
        return "spacious"


def _get_pdf_page_count(pdf_path: str) -> int:
    """获取 PDF 页数"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        count = doc.page_count
        doc.close()
        return count
    except ImportError:
        logger.warning("PyMuPDF 未安装，无法检测页数")
        return 1
    except Exception as e:
        logger.warning(f"检测页数失败: {e}")
        return 1


def _get_last_page_fill_ratio(pdf_path: str) -> float:
    """
    获取最后一页的填充率 (0.0 - 1.0)
    """
    try:
        import fitz
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            doc.close()
            return 1.0

        last_page = doc[-1]
        # 获取页面上所有文本块的边界
        blocks = last_page.get_text("dict")["blocks"]

        if not blocks:
            doc.close()
            return 0.0

        # 找到最底部的内容位置
        max_y = 0
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        bbox = span["bbox"]
                        max_y = max(max_y, bbox[3])

        # 计算填充率（A4 高度约 842 点）
        page_height = last_page.rect.height
        fill_ratio = max_y / page_height if page_height > 0 else 1.0

        doc.close()
        return fill_ratio

    except ImportError:
        logger.warning("PyMuPDF 未安装，无法检测填充率")
        return 0.85
    except Exception as e:
        logger.warning(f"检测填充率失败: {e}")
        return 0.85


def _inject_style_variables(html_content: str, preset: str) -> str:
    """
    将样式变量注入到 HTML 中
    """
    style = STYLE_PRESETS.get(preset, STYLE_PRESETS["standard"])

    # 🔴 ultra_compact 模式：禁用分页保护，允许内容在任意位置断开
    page_break_override = ""
    if preset == "ultra_compact":
        page_break_override = """
        /* 禁用分页保护，优先压缩到1页 */
        section, .entry, h2 {
            page-break-inside: auto !important;
            break-inside: auto !important;
            page-break-after: auto !important;
            break-after: auto !important;
        }
        """

    css_override = f"""
    <style>
        /* 自适应样式覆盖 - {preset} 模式 */
        body {{
            font-size: {style["font_size"]} !important;
            line-height: {style["line_height"]} !important;
            padding: {style["padding"]} !important;
        }}
        h2 {{
            margin-top: {style["section_margin"]} !important;
            page-break-after: avoid !important;
            break-after: avoid !important;
        }}
        .entry {{
            margin-bottom: {style["entry_margin"]} !important;
        }}
        /* 允许 section 和 entry 跨页 */
        section, .entry {{
            page-break-inside: auto !important;
            break-inside: auto !important;
        }}
        /* 关键：页面底部至少保留3行，顶部至少保留3行 */
        /* 如果只剩1-2行就会自动换页 */
        p, li, .entry-header, .entry-subtitle {{
            orphans: 3 !important;
            widows: 3 !important;
        }}
        ul {{
            orphans: 3 !important;
            widows: 3 !important;
        }}
        {page_break_override}
    </style>
    </head>
    """

    return html_content.replace("</head>", css_override)


async def _generate_pdf_with_playwright(html_content: str, output_path: str) -> None:
    """使用 Playwright 生成 PDF (异步版本)，带智能分页"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_content)

        # 🔴 智能分页：如果 section 标题后只能再写 1-2 行，就整个翻页
        await page.evaluate("""
        () => {
            const PAGE_HEIGHT = 1123;  // A4 页面高度 (px at 96dpi)
            const MIN_CONTENT_HEIGHT = 80;  // 至少需要 3 行内容的高度 (~80px)

            // 获取所有 section 标题
            const headers = document.querySelectorAll('section h2');

            headers.forEach(header => {
                const rect = header.getBoundingClientRect();
                const headerTop = rect.top;

                // 计算当前在第几页
                const currentPage = Math.floor(headerTop / PAGE_HEIGHT);
                // 计算这一页剩余空间
                const pageBottom = (currentPage + 1) * PAGE_HEIGHT;
                const remainingSpace = pageBottom - headerTop;

                // 如果剩余空间不够放标题 + 3行内容，就给 section 加分页
                if (remainingSpace < (rect.height + MIN_CONTENT_HEIGHT)) {
                    const section = header.closest('section');
                    if (section) {
                        section.style.pageBreakBefore = 'always';
                        section.style.breakBefore = 'page';
                    }
                }
            });
        }
        """)

        await page.pdf(
            path=output_path,
            format='A4',
            print_background=True,
            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
        )
        await browser.close()


async def generate_resume_pdf(resume_data: Dict[str, Any], output_path: str) -> None:
    """
    生成简历 PDF（带自适应排版）- 异步版本

    流程:
    1. 根据内容量预估选择基础样式
    2. 生成 PDF
    3. 检测填充率，如果不理想则微调重新生成
    """
    try:
        # 清理数据
        resume_data = clean_resume_data(resume_data)

        # 调试：打印 linkedin 字段确认 URL 处理
        if 'linkedin' in resume_data:
            print(f"[PDF] LinkedIn URL (处理后): {resume_data.get('linkedin')}")

        # 获取模板
        base_dir = Path(__file__).parent.parent
        template_dir = base_dir / "data" / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("cv_template.html")

        # 渲染基础 HTML
        html_content = template.render(**resume_data)

        # 第一步：根据内容量预估选择样式
        preset = _estimate_content_volume(resume_data)
        print(f"[PDF] 预估样式: {preset}")

        # 注入样式并生成第一版 PDF
        styled_html = _inject_style_variables(html_content, preset)
        await _generate_pdf_with_playwright(styled_html, output_path)

        # 第二步：检测填充率并微调
        page_count = _get_pdf_page_count(output_path)
        fill_ratio = _get_last_page_fill_ratio(output_path)

        if page_count == 1:
            print(f"[PDF] 第一次生成: {page_count}页, 填充率: {fill_ratio:.1%}")
        else:
            print(f"[PDF] 第一次生成: {page_count}页, 第{page_count}页填充率: {fill_ratio:.1%}")

        # 微调逻辑
        need_regenerate = False
        new_preset = preset

        if page_count == 1 and fill_ratio < 0.7:
            # 单页但内容太少，用更宽松的样式让页面更饱满
            print(f"[PDF] 检测到单页填充率过低 ({fill_ratio:.1%} < 70%)，尝试放大样式")
            if preset == "compact":
                new_preset = "standard"
                need_regenerate = True
            elif preset == "standard":
                new_preset = "spacious"
                need_regenerate = True

        elif page_count >= 2 and fill_ratio < 0.3:
            # 🔴 只有第二页内容太少（不到 30%）才压缩
            # 如果第二页 >= 30%，说明内容确实需要 2 页，不强制压缩
            print(f"[PDF] 检测到第{page_count}页填充率过低 ({fill_ratio:.1%} < 30%)，尝试压缩")
            if preset == "spacious":
                new_preset = "standard"
                need_regenerate = True
            elif preset == "standard":
                new_preset = "compact"
                need_regenerate = True
            # 🔴 不再继续压缩到 ultra_compact，避免字太小

        # 需要重新生成
        if need_regenerate:
            print(f"[PDF] 微调样式: {preset} → {new_preset}")
            styled_html = _inject_style_variables(html_content, new_preset)
            await _generate_pdf_with_playwright(styled_html, output_path)

            # 再次检测
            new_page_count = _get_pdf_page_count(output_path)
            new_fill_ratio = _get_last_page_fill_ratio(output_path)
            print(f"[PDF] 第二次生成: {new_page_count}页, 填充率: {new_fill_ratio:.1%}")

            # 如果还是2页且第二页<50%，继续压缩
            if new_page_count >= 2 and new_fill_ratio < 0.5 and new_preset != "ultra_compact":
                print(f"[PDF] 仍需压缩，继续尝试...")
                if new_preset == "standard":
                    final_preset = "compact"
                elif new_preset == "compact":
                    final_preset = "ultra_compact"
                else:
                    final_preset = "ultra_compact"

                print(f"[PDF] 微调样式: {new_preset} → {final_preset}")
                styled_html = _inject_style_variables(html_content, final_preset)
                await _generate_pdf_with_playwright(styled_html, output_path)

                final_page_count = _get_pdf_page_count(output_path)
                final_fill_ratio = _get_last_page_fill_ratio(output_path)
                print(f"[PDF] 第三次生成: {final_page_count}页, 填充率: {final_fill_ratio:.1%}")

        logger.info(f"✅ PDF 生成成功: {output_path}")

    except Exception as e:
        logger.error(f"❌ PDF 生成失败: {e}")
        raise RuntimeError(f"PDF 生成失败: {str(e)}")


async def generate_cover_letter_pdf(cover_letter_text: str, output_path: str) -> None:
    """生成求职信 PDF (异步版本)"""
    try:
        base_dir = Path(__file__).parent.parent
        template_dir = base_dir / "data" / "templates"

        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("cover_letter_template.html")

        html_content = template.render(cover_letter=cover_letter_text)
        await _generate_pdf_with_playwright(html_content, output_path)

        logger.info(f"✅ Cover Letter PDF 生成成功: {output_path}")

    except Exception as e:
        logger.error(f"❌ Cover Letter PDF 生成失败: {e}")
        raise RuntimeError(f"PDF 生成失败: {str(e)}")
