"""
测试脚本 4: 测试单个职位投递
⚠️ 这个测试会真实投递简历！请使用测试职位或已投递过的职位
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.apply_bot import JobsDBApplyBot, ApplyJobInfo
from core.llm_engine import LLMEngine
import time


def test_single_job_apply():
    """测试单个职位的投递流程"""
    print("=" * 50)
    print("测试: 单个职位投递")
    print("=" * 50)

    # 检查环境变量
    username = os.getenv("JOBSDB_USERNAME")
    password = os.getenv("JOBSDB_PASSWORD")

    if not username or not password:
        print("\n❌ 错误: 未配置 JobsDB 账号")
        return False

    # 准备测试数据
    print("\n⚠️ 重要: 请输入一个测试职位的 URL")
    print("建议使用:")
    print("1. 已经投递过的职位（测试会检测到 '已投递' 状态）")
    print("2. 或一个您确实想投递的职位\n")

    job_url = input("请输入职位 URL (或按 Enter 使用默认测试): ").strip()

    # 如果用户没有输入，使用一个示例（不会真实投递）
    if not job_url:
        job_url = "https://hk.jobsdb.com/job/12345678"
        print(f"使用测试 URL: {job_url}")
        print("（这是一个假的 URL，用于测试流程）\n")

    # 创建测试职位信息
    test_job = ApplyJobInfo(
        job_id="test_001",
        title="Software Engineer",
        company="Test Company",
        location="Hong Kong",
        job_url=job_url,
        jd_text="""
        We are looking for a Software Engineer with Python experience.
        Requirements:
        - 2+ years of Python development
        - Experience with web frameworks
        - Good communication skills
        """,
        score=85.0
    )

    # 准备候选人信息
    candidate_profile = {
        "resume_text": """
        John Doe
        Software Engineer with 3 years of Python experience.
        Skills: Python, Django, React, Docker
        """,
        "name": "John Doe"
    }

    print("\n职位信息:")
    print(f"  标题: {test_job.title}")
    print(f"  公司: {test_job.company}")
    print(f"  URL: {test_job.job_url}")
    print(f"  匹配分数: {test_job.score}")

    confirm = input("\n确认要继续测试吗? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("测试已取消")
        return False

    try:
        # 初始化 LLM 引擎
        print("\n1. 初始化 LLM 引擎...")
        llm = LLMEngine()
        print("   ✅ 完成")

        # 初始化 Apply Bot
        print("\n2. 初始化 Apply Bot...")
        with JobsDBApplyBot(
            username=username,
            password=password,
            llm_engine=llm,
            headless=False,  # 显示浏览器
            allow_manual_captcha=True,
            captcha_timeout=300
        ) as bot:
            print("   ✅ 完成")

            # 登录
            print("\n3. 登录 JobsDB...")
            if not bot.ensure_logged_in():
                print("   ❌ 登录失败")
                return False
            print("   ✅ 登录成功")

            # 生成 Cover Letter
            print("\n4. 生成 Cover Letter...")
            cover_letter = bot.generate_cover_letter(candidate_profile, test_job)
            print("   ✅ 完成")
            print("\n生成的 Cover Letter (前 200 字符):")
            print("-" * 50)
            print(cover_letter[:200] + "...")
            print("-" * 50)

            # 执行投递
            print("\n5. 开始投递...")
            print("   ⚠️ 如果出现验证码，请在浏览器中手动完成")

            result = bot.apply_to_job(
                test_job,
                candidate_profile=candidate_profile,
                cover_letter=cover_letter
            )

            # 显示结果
            print("\n6. 投递结果:")
            print(f"   状态: {result.status.value}")
            print(f"   消息: {result.message}")

            if result.status.value == "success":
                print("\n   ✅ 投递成功！")
                print("   保持浏览器打开 10 秒，您可以查看结果...")
                time.sleep(10)
                return True
            elif result.status.value == "already_applied":
                print("\n   ℹ️ 这个职位已经投递过了")
                print("   这是正常的，说明检测功能工作正常")
                return True
            else:
                print(f"\n   ❌ 投递失败: {result.message}")
                print("   保持浏览器打开 10 秒，您可以查看页面...")
                time.sleep(10)
                return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 开始测试单个职位投递\n")
    print("⚠️ 重要提示:")
    print("1. 这个测试会真实投递简历（如果职位未投递过）")
    print("2. 建议使用已投递过的职位进行测试")
    print("3. 或使用一个您确实想投递的职位")
    print("4. 浏览器会保持打开状态，请不要手动关闭\n")

    input("按 Enter 键开始测试...")

    success = test_single_job_apply()

    # 总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)

    if success:
        print("✅ 测试通过！")
        print("\n观察到的情况:")
        print("1. Cover Letter 生成成功")
        print("2. 能够打开职位页面")
        print("3. 能够检测已投递状态（如果适用）")
        print("4. 投递流程正常工作")
        print("\n下一步: 可以测试批量投递功能")
    else:
        print("❌ 测试失败")
        print("\n可能的原因:")
        print("1. 职位 URL 无效")
        print("2. 页面结构变化（选择器失效）")
        print("3. 网络问题")
        print("4. 验证码未正确处理")
