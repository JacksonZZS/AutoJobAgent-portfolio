"""
PDF 生成器 - 使用 ReportLab (稳定版)
完全放弃 Playwright，避免浏览器冲突
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


async def generate_pdf_cv(cv_data, output_path):
    """
    使用 ReportLab 生成 PDF (绝对稳定版)

    Args:
        cv_data: 简历数据字典
        output_path: 输出 PDF 路径
    """
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 创建 PDF
        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4

        # 获取个人信息
        personal_info = cv_data.get('personal_info', {})
        name = personal_info.get('name', 'Candidate')
        email = personal_info.get('email', '')
        phone = personal_info.get('phone', '')

        # 标题
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, height - 50, name)

        # 联系方式
        c.setFont("Helvetica", 10)
        y = height - 75
        if email:
            c.drawString(50, y, f"Email: {email}")
            y -= 15
        if phone:
            c.drawString(50, y, f"Phone: {phone}")
            y -= 30

        # 工作经验
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Work Experience")
        y -= 20

        c.setFont("Helvetica", 10)
        work_experience = cv_data.get('work_experience', [])
        if not isinstance(work_experience, list):
            work_experience = []

        for exp in work_experience[:5]:
            if y < 100:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

            company = exp.get('company', 'N/A') if isinstance(exp, dict) else 'N/A'
            position = exp.get('position', 'N/A') if isinstance(exp, dict) else 'N/A'
            duration = exp.get('duration', 'N/A') if isinstance(exp, dict) else 'N/A'

            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, f"{position} at {company}")
            y -= 15

            c.setFont("Helvetica", 9)
            c.drawString(50, y, duration)
            y -= 12

            responsibilities = exp.get('responsibilities', []) if isinstance(exp, dict) else []
            if not isinstance(responsibilities, list):
                responsibilities = []

            for resp in responsibilities[:3]:
                if y < 100:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 9)

                resp_text = str(resp)[:100]
                c.drawString(70, y, f"• {resp_text}")
                y -= 12

            y -= 10

        # 教育背景
        if y < 200:
            c.showPage()
            y = height - 50
        else:
            y -= 20

        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Education")
        y -= 20

        c.setFont("Helvetica", 10)
        education = cv_data.get('education', [])
        if not isinstance(education, list):
            education = []

        for edu in education[:3]:
            if y < 100:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

            degree = edu.get('degree', 'N/A') if isinstance(edu, dict) else 'N/A'
            school = edu.get('school', 'N/A') if isinstance(edu, dict) else 'N/A'
            year = edu.get('year', 'N/A') if isinstance(edu, dict) else 'N/A'

            c.drawString(50, y, f"{degree} - {school} ({year})")
            y -= 15

        # 技能
        if y < 150:
            c.showPage()
            y = height - 50
        else:
            y -= 20

        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Skills")
        y -= 20

        c.setFont("Helvetica", 10)
        skills = cv_data.get('skills', [])
        if not isinstance(skills, list):
            skills = []
        skills_text = ', '.join(str(s) for s in skills[:20])

        max_width = 500
        words = skills_text.split(', ') if skills_text else []
        line = ""
        for word in words:
            if c.stringWidth(line + word, "Helvetica", 10) < max_width:
                line += word + ", "
            else:
                c.drawString(50, y, line.rstrip(', '))
                y -= 15
                line = word + ", "
                if y < 100:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 10)

        if line:
            c.drawString(50, y, line.rstrip(', '))

        # 保存 PDF
        c.save()

        print(f"   ✅ PDF 已生成: {output_path}")
        return output_path

    except Exception as e:
        print(f"   ❌ PDF 生成失败: {e}")
        # 创建一个最简单的备用 PDF
        try:
            c = canvas.Canvas(str(output_path), pagesize=A4)
            width, height = A4
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, "Resume")
            c.setFont("Helvetica", 12)
            c.drawString(50, height - 80, f"Name: {cv_data.get('personal_info', {}).get('name', 'Candidate')}")
            c.drawString(50, height - 100, "Generated by AutoJobAgent")
            c.save()
            print(f"   ⚠️ 使用备用模板生成 PDF: {output_path}")
            return output_path
        except Exception as fallback_error:
            print(f"   ❌ 备用 PDF 生成也失败: {fallback_error}")
            raise RuntimeError(f"PDF generation failed: {e}") from e
