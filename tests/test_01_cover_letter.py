"""
测试脚本 1: 测试 Cover Letter 生成功能
这是最基础的测试，不涉及浏览器操作
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_engine import LLMEngine


def test_cover_letter_generation():
    """测试 Cover Letter 生成功能"""
    print("=" * 50)
    print("测试 1: Cover Letter 生成")
    print("=" * 50)

    # 初始化 LLM 引擎
    print("\n1. 初始化 LLM 引擎...")
    try:
        llm = LLMEngine()
        print("   ✅ LLM 引擎初始化成功")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False

    # 准备测试数据
    candidate_profile = {
        "resume_text": """
        John Doe
        Email: john.doe@gmail.com
        Phone: +852 1234 5678

        PROFESSIONAL SUMMARY
        Experienced Software Engineer with 3+ years in Python and web development.

        EXPERIENCE
        - Software Engineer at Tech Corp (2021-2024)
        - Developed RESTful APIs using Python/Django
        - Led migration to microservices architecture

        SKILLS
        Python, JavaScript, React, Django, Docker, AWS
        """,
        "name": "John Doe"
    }

    job_info = {
        "title": "Senior Software Engineer",
        "company": "Amazing Tech Ltd",
        "location": "Hong Kong",
        "jd_text": """
        We are seeking a Senior Software Engineer to join our team.

        Requirements:
        - 3+ years of Python development experience
        - Experience with Django or Flask
        - Knowledge of Docker and cloud platforms
        - Strong problem-solving skills

        Responsibilities:
        - Design and develop scalable web applications
        - Collaborate with cross-functional teams
        - Mentor junior developers
        """
    }

    # 测试生成 Cover Letter
    print("\n2. 生成 Cover Letter...")
    try:
        cover_letter = llm.generate_cover_letter(candidate_profile, job_info)
        print("   ✅ Cover Letter 生成成功")
        print("\n" + "=" * 50)
        print("生成的 Cover Letter:")
        print("=" * 50)
        print(cover_letter)
        print("=" * 50)
        print(f"\n   长度: {len(cover_letter)} 字符")

        # 验证基本内容
        if job_info["title"] in cover_letter and job_info["company"] in cover_letter:
            print("   ✅ Cover Letter 包含职位和公司名称")
        else:
            print("   ⚠️ Cover Letter 可能缺少关键信息")

        return True

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fallback_template():
    """测试异常时的 fallback 模板"""
    print("\n" + "=" * 50)
    print("测试 2: Fallback 模板（模拟 API 失败）")
    print("=" * 50)

    # 创建一个会失败的 LLM 引擎
    print("\n使用错误的 API Key 模拟失败...")

    os.environ["ANTHROPIC_API_KEY"] = "invalid_key_for_testing"

    try:
        llm = LLMEngine()

        candidate_profile = {"name": "Test User"}
        job_info = {
            "title": "Test Position",
            "company": "Test Company",
            "location": "Hong Kong",
            "jd_text": "Test JD"
        }

        cover_letter = llm.generate_cover_letter(candidate_profile, job_info)

        if "Dear Hiring Manager" in cover_letter and "Test Position" in cover_letter:
            print("   ✅ Fallback 模板工作正常")
            print("\n生成的默认模板:")
            print("-" * 50)
            print(cover_letter)
            print("-" * 50)
            return True
        else:
            print("   ❌ Fallback 模板可能有问题")
            return False

    except Exception as e:
        print(f"   ❌ 意外错误: {e}")
        return False


if __name__ == "__main__":
    print("🧪 开始测试 Cover Letter 生成功能\n")

    # 测试 1: 正常生成
    success1 = test_cover_letter_generation()

    # 测试 2: Fallback 模板
    success2 = test_fallback_template()

    # 总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"测试 1 (正常生成): {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"测试 2 (Fallback): {'✅ 通过' if success2 else '❌ 失败'}")

    if success1 and success2:
        print("\n🎉 所有测试通过！可以继续下一步测试。")
    else:
        print("\n⚠️ 部分测试失败，请检查配置。")
