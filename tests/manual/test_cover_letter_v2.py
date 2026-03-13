#!/usr/bin/env python3
"""
测试优化后的 Cover Letter 生成功能
验证动态日期和智能收件人处理
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from core.llm_engine import LLMEngine

def print_section(title):
    """打印分隔线"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_cover_letter_with_hr_name():
    """测试场景 1: 有 HR 姓名"""
    print_section("测试场景 1: 有 HR 姓名")

    llm = LLMEngine()

    candidate_profile = {
        "name": "Jackson Zhang",
        "resume_text": """
        Jackson Zhang
        Software Engineer with 3 years of experience in Python, Django, and React.

        Experience:
        - Software Engineer at TechCorp (2021-2024)
          - Developed RESTful APIs using Django
          - Built responsive web applications with React
          - Improved system performance by 40%

        Skills: Python, Django, React, PostgreSQL, Docker
        """
    }

    job_info = {
        "title": "Senior Python Developer",
        "company": "Google",
        "location": "Hong Kong",
        "jd_text": "We are looking for a Senior Python Developer with Django experience...",
        "hr_name": "Sarah Johnson"  # 🔴 提供 HR 姓名
    }

    print("\n📝 生成 Cover Letter...")
    cover_letter = llm.generate_cover_letter(candidate_profile, job_info)

    print("\n✅ 生成的 Cover Letter:")
    print("-" * 60)
    print(cover_letter)
    print("-" * 60)

    # 验证格式
    current_date = datetime.now().strftime("%B %d, %Y")

    checks = {
        "包含当前日期": current_date in cover_letter,
        "包含公司名称": "Google" in cover_letter,
        "使用个性化收件人": "Dear Sarah Johnson," in cover_letter,
        "使用正确的结尾": "Yours sincerely," in cover_letter,
        "包含候选人姓名": "Jackson Zhang" in cover_letter
    }

    print("\n🔍 格式验证:")
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")

    return all(checks.values())

def test_cover_letter_without_hr_name():
    """测试场景 2: 无 HR 姓名"""
    print_section("测试场景 2: 无 HR 姓名")

    llm = LLMEngine()

    candidate_profile = {
        "name": "Jackson Zhang",
        "resume_text": """
        Jackson Zhang
        Software Engineer with 3 years of experience in Python, Django, and React.
        """
    }

    job_info = {
        "title": "Backend Developer",
        "company": "Microsoft",
        "location": "Hong Kong",
        "jd_text": "We are looking for a Backend Developer...",
        # 🔴 不提供 hr_name
    }

    print("\n📝 生成 Cover Letter...")
    cover_letter = llm.generate_cover_letter(candidate_profile, job_info)

    print("\n✅ 生成的 Cover Letter:")
    print("-" * 60)
    print(cover_letter)
    print("-" * 60)

    # 验证格式
    current_date = datetime.now().strftime("%B %d, %Y")

    checks = {
        "包含当前日期": current_date in cover_letter,
        "包含公司名称": "Microsoft" in cover_letter,
        "使用默认收件人": "Dear Hiring Manager," in cover_letter,
        "使用正确的结尾": "Yours sincerely," in cover_letter,
        "包含候选人姓名": "Jackson Zhang" in cover_letter
    }

    print("\n🔍 格式验证:")
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")

    return all(checks.values())

def test_cover_letter_format_structure():
    """测试场景 3: 验证完整格式结构"""
    print_section("测试场景 3: 验证完整格式结构")

    llm = LLMEngine()

    candidate_profile = {
        "name": "Jackson Zhang",
        "resume_text": "Software Engineer with Python experience"
    }

    job_info = {
        "title": "Python Developer",
        "company": "Amazon",
        "location": "Hong Kong",
        "jd_text": "Python developer needed...",
        "hr_name": "John Smith"
    }

    print("\n📝 生成 Cover Letter...")
    cover_letter = llm.generate_cover_letter(candidate_profile, job_info)

    print("\n✅ 生成的 Cover Letter:")
    print("-" * 60)
    print(cover_letter)
    print("-" * 60)

    # 验证结构顺序
    current_date = datetime.now().strftime("%B %d, %Y")

    # 检查各部分的位置
    date_pos = cover_letter.find(current_date)
    company_pos = cover_letter.find("Amazon")
    recipient_pos = cover_letter.find("Dear John Smith,")
    closing_pos = cover_letter.find("Yours sincerely,")
    name_pos = cover_letter.find("Jackson Zhang")

    print("\n🔍 结构顺序验证:")
    print(f"  日期位置: {date_pos}")
    print(f"  公司位置: {company_pos}")
    print(f"  收件人位置: {recipient_pos}")
    print(f"  结尾位置: {closing_pos}")
    print(f"  姓名位置: {name_pos}")

    # 验证顺序是否正确
    order_correct = (
        date_pos < company_pos < recipient_pos < closing_pos < name_pos
    )

    if order_correct:
        print("\n  ✅ 格式结构顺序正确")
    else:
        print("\n  ❌ 格式结构顺序错误")

    return order_correct

def main():
    print_section("🚀 Cover Letter 优化功能测试")
    print("测试动态日期和智能收件人处理...")

    results = []

    try:
        # 测试 1: 有 HR 姓名
        result1 = test_cover_letter_with_hr_name()
        results.append(("有 HR 姓名", result1))

        # 测试 2: 无 HR 姓名
        result2 = test_cover_letter_without_hr_name()
        results.append(("无 HR 姓名", result2))

        # 测试 3: 格式结构
        result3 = test_cover_letter_format_structure()
        results.append(("格式结构", result3))

    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 汇总结果
    print_section("📊 测试结果汇总")

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {test_name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 所有测试通过！Cover Letter 优化功能正常工作。")
        print("\n✨ 新功能:")
        print("  1. ✅ 动态日期注入 - 每次生成都使用当前日期")
        print("  2. ✅ 智能收件人处理 - 自动识别 HR 姓名")
        print("  3. ✅ 标准格式约束 - 确保专业的商务信函格式")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
