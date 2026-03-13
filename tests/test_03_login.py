"""
测试脚本 3: 测试登录功能（需要真实账号）
⚠️ 这个测试需要您在 .env 中配置真实的 JobsDB 账号
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.apply_bot import JobsDBApplyBot
import time


def test_login():
    """测试登录功能"""
    print("=" * 50)
    print("测试: JobsDB 登录")
    print("=" * 50)

    # 检查环境变量
    username = os.getenv("JOBSDB_USERNAME")
    password = os.getenv("JOBSDB_PASSWORD")

    if not username or not password:
        print("\n❌ 错误: 未配置 JobsDB 账号")
        print("\n请在 .env 文件中添加:")
        print("JOBSDB_USERNAME=your_email@example.com")
        print("JOBSDB_PASSWORD=your_password")
        return False

    print(f"\n使用账号: {username}")
    print("密码: " + "*" * len(password))

    try:
        with JobsDBApplyBot(
            username=username,
            password=password,
            headless=False,  # 显示浏览器，方便观察
            allow_manual_captcha=True,  # 允许手动处理验证码
            captcha_timeout=300  # 5 分钟超时
        ) as bot:
            print("\n1. 浏览器已启动")

            print("\n2. 尝试登录...")
            print("   ⚠️ 如果出现验证码，请在浏览器中手动完成")

            login_success = bot.ensure_logged_in()

            if login_success:
                print("\n   ✅ 登录成功！")

                # 验证登录状态
                print("\n3. 验证登录状态...")
                bot._page.goto("https://hk.jobsdb.com/", timeout=30000)
                time.sleep(2)

                # 检查是否有账户菜单
                account_menu = bot._page.query_selector(bot.selectors["logged_in_indicator"])
                if account_menu:
                    print("   ✅ 登录状态验证成功")
                    print("\n4. Cookie 已保存，下次可以自动登录")

                    # 显示 cookie 路径
                    print(f"   Cookie 路径: {bot.cookie_path}")

                    print("\n5. 保持浏览器打开 10 秒，您可以查看登录状态...")
                    time.sleep(10)

                    return True
                else:
                    print("   ⚠️ 无法验证登录状态")
                    return False
            else:
                print("\n   ❌ 登录失败")
                return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cookie_reuse():
    """测试 Cookie 复用（需要先运行 test_login）"""
    print("\n" + "=" * 50)
    print("测试: Cookie 复用（自动登录）")
    print("=" * 50)

    cookie_path = os.getenv("JOBSDB_COOKIE_PATH", "data/sessions/jobsdb_cookies.json")

    if not os.path.exists(cookie_path):
        print(f"\n⚠️ Cookie 文件不存在: {cookie_path}")
        print("请先运行 test_login() 以保存 Cookie")
        return False

    print(f"\n找到 Cookie 文件: {cookie_path}")

    try:
        with JobsDBApplyBot(
            headless=False,
            allow_manual_captcha=False  # 不应该需要验证码
        ) as bot:
            print("\n1. 浏览器已启动")
            print("2. 尝试使用 Cookie 自动登录...")

            login_success = bot.ensure_logged_in()

            if login_success:
                print("   ✅ 使用 Cookie 自动登录成功！")

                print("\n3. 保持浏览器打开 5 秒...")
                time.sleep(5)

                return True
            else:
                print("   ❌ Cookie 可能已过期，需要重新登录")
                return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 开始测试登录功能\n")
    print("⚠️ 重要提示:")
    print("1. 这个测试需要真实的 JobsDB 账号")
    print("2. 如果出现验证码，请在浏览器中手动完成")
    print("3. 浏览器会保持打开状态，请不要手动关闭")
    print("4. 测试完成后浏览器会自动关闭\n")

    input("按 Enter 键开始测试...")

    # 测试 1: 登录
    print("\n" + "=" * 60)
    print("第一部分: 测试登录并保存 Cookie")
    print("=" * 60)
    success1 = test_login()

    if success1:
        # 测试 2: Cookie 复用
        print("\n" + "=" * 60)
        print("第二部分: 测试 Cookie 复用")
        print("=" * 60)
        input("\n按 Enter 键继续测试 Cookie 复用...")
        success2 = test_cookie_reuse()
    else:
        success2 = False
        print("\n⚠️ 跳过 Cookie 复用测试（登录失败）")

    # 总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"测试 1 (登录): {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"测试 2 (Cookie 复用): {'✅ 通过' if success2 else '❌ 失败'}")

    if success1 and success2:
        print("\n🎉 所有测试通过！登录功能工作正常。")
        print("\n下一步: 可以测试完整的投递流程")
    else:
        print("\n⚠️ 部分测试失败。")
        if not success1:
            print("\n可能的原因:")
            print("1. 账号密码错误")
            print("2. 网络问题")
            print("3. JobsDB 网站结构变化（选择器失效）")
            print("4. 验证码未正确处理")
