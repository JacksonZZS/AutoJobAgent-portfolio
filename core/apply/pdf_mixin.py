# core/apply/pdf_mixin.py
"""PDF generation mixin for JobsDBApplyBot."""

import logging
import base64
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFGenerationMixin:
    """Handles PDF generation for resumes and cover letters."""

    def _generate_pdf_from_html(self, html_content: str, output_path: str):
        """
        使用 ReportLab 生成 PDF（避免浏览器冲突）

        Args:
            html_content: HTML 内容字符串（已弃用，保留参数兼容性）
            output_path: 输出 PDF 文件路径
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            import re

            # 简单的 HTML 解析（提取文本）
            text_content = re.sub('<[^<]+?>', '', html_content)
            text_content = text_content.replace('&nbsp;', ' ').strip()

            # 创建 PDF
            c = canvas.Canvas(str(output_path), pagesize=A4)
            width, height = A4

            c.setFont("Helvetica", 10)
            y = height - 50

            # 简单的文本渲染
            lines = text_content.split('\n')
            for line in lines[:100]:  # 限制行数
                if y < 50:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 10)

                line = line.strip()
                if line:
                    # 限制每行长度
                    if len(line) > 100:
                        line = line[:100] + "..."
                    c.drawString(50, y, line)
                    y -= 15

            c.save()
            logger.info(f"✅ PDF 已生成: {output_path}")

        except Exception as e:
            logger.error(f"❌ PDF 生成失败: {e}")
            raise

    def _generate_custom_resume_pdf(self, candidate_profile: dict, job_info, output_path: str) -> str:
        """生成定制化简历 (使用 JSON + HTML 模板)"""
        logger.info("📝 正在生成定制化简历...")

        try:
            from core.user_identity import get_user_identity, validate_user_for_cv
            from jinja2 import Template

            # 验证用户信息
            if not validate_user_for_cv(self.user_id):
                raise ValueError(f"User {self.user_id} information incomplete, cannot generate CV")

            user_identity = get_user_identity(self.user_id)

            # 1. 获取简历内容 (优先读文件)
            resume_text = ""
            if self.cv_path and Path(self.cv_path).exists():
                try:
                    import pdfplumber
                    with pdfplumber.open(self.cv_path) as pdf:
                        resume_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
                    logger.info(f"✅ 已读取本地简历原件: {len(resume_text)} 字符")
                except:
                    pass

            if not resume_text:
                resume_text = candidate_profile.get("resume_text", "")
            if not resume_text:
                raise ValueError("无法获取简历内容！")

            # 2. 调用 LLM 生成数据
            if not self.llm_engine:
                raise ValueError("LLM Engine not ready")

            logger.info("🤖 正在调用 AI 生成定制简历数据...")
            resume_data = self.llm_engine.generate_resume_data(
                resume_text=resume_text,
                transcript_text="",
                jd_text=job_info.jd_text,
                user_real_name="",
                user_email="",
                user_phone="",
                user_linkedin=user_identity.linkedin or "",
                user_github=user_identity.github or ""
            )

            if not resume_data:
                raise ValueError("LLM 生成简历数据失败：返回空值")

            if not isinstance(resume_data, dict):
                raise ValueError(f"LLM 返回数据类型错误，期望 dict，实际为 {type(resume_data)}")

            # 3. 读取 HTML 模板
            template_path = Path("data/templates/cv_template.html")
            if not template_path.exists():
                raise FileNotFoundError(f"❌ 找不到简历模版文件: {template_path}")

            with open(template_path, 'r', encoding='utf-8') as f:
                html_template = f.read()

            # 4. 准备渲染上下文
            render_context = {
                "name": resume_data.get('name', ''),
                "email": resume_data.get('email', ''),
                "phone": resume_data.get('phone', ''),
                "linkedin": resume_data.get('linkedin', ''),
                "github": resume_data.get('github', ''),
                "summary": resume_data.get('summary', ''),
                "experience": resume_data.get('experience', []),
                "projects": resume_data.get('projects', []),
                "skills": resume_data.get('skills', []),
                "education": resume_data.get('education', {}),
                "languages": resume_data.get('languages', []),
                "work_eligibility": resume_data.get('work_eligibility', ''),
                "availability": resume_data.get('availability', '')
            }

            # 5. 调用 pdf_generator 生成 PDF（带自适应排版）
            from core.pdf_generator import generate_resume_pdf
            logger.info("🖨️ 调用 pdf_generator 生成自适应 PDF...")
            # 🔴 generate_resume_pdf 是 async 函数，需要用 asyncio.run()
            asyncio.run(generate_resume_pdf(resume_data=render_context, output_path=output_path))
            logger.info(f"✅ PDF 生成成功: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"❌ 简历生成失败: {e}")
            raise

    def _generate_cover_letter_pdf(
        self,
        cover_letter_text: str,
        job_info,
        output_path: str
    ) -> str:
        """
        将求职信文本转换为 PDF（使用 ReportLab）

        Args:
            cover_letter_text: 求职信文本
            job_info: 职位信息
            output_path: 输出路径

        Returns:
            PDF 文件路径
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas as pdf_canvas
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.enums import TA_LEFT

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )

            styles = getSampleStyleSheet()
            story = []

            # 正文样式
            body_style = styles['Normal']
            body_style.fontSize = 11
            body_style.leading = 16
            body_style.alignment = TA_LEFT

            # 分段处理
            paragraphs = cover_letter_text.split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if para:
                    # 处理单行换行
                    para = para.replace('\n', '<br/>')
                    story.append(Paragraph(para, body_style))
                    story.append(Spacer(1, 12))

            doc.build(story)
            logger.info(f"✅ Cover Letter PDF 生成成功: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"❌ Cover Letter PDF 生成失败: {e}")
            # Fallback: 使用简单方法
            try:
                self._generate_pdf_from_html(
                    f"<pre>{cover_letter_text}</pre>",
                    output_path
                )
                return str(output_path)
            except:
                raise

    def _get_file_as_data_uri(self, file_path: str) -> str:
        """
        将文件转换为 Data URI 以便在浏览器中下载

        Args:
            file_path: 文件路径

        Returns:
            Data URI 格式字符串 (data:application/pdf;base64,...)
        """
        try:
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            return f"data:application/pdf;base64,{encoded}"
        except Exception as e:
            logger.error(f"Base64转换失败: {e}")
            return "#"
