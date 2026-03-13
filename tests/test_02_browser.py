"""
测试脚本 2: 测试浏览器启动和关闭
测试 Playwright 是否正确安装，浏览器能否正常启动
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.apply_bot import JobsDBApplyBot
import time


def test_browser_lifecycle():
    """测试浏览器生命周期管理"""
    print("=" * 50)
    print("测试: 浏览器启动和关闭")
    print("=" * 50)

    print("\n1. 测试手动启动/关闭...")
    try:
        bot = JobsDBApplyBot(
            headless=False,  # 显示浏览器窗口
            allow_manual_captcha=False  # 测试时不需要验证码处理
        )

        print("   启动浏览器...")
        bot.start()
        print("   ✅ 浏览器启动成功")

        print("   等待 3 秒...")
        time.sleep(3)

        print("   关闭浏览器...")
        bot.close()
        print("   ✅ 浏览器关闭成功")

        return True

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_manager():
    """测试 context manager 方式"""
    print("\n" + "=" * 50)
    print("测试: Context Manager (推荐方式)")
    print("=" * 50)

    print("\n使用 'with' 语句管理浏览器...")
    try:
        with JobsDBApplyBot(
            headless=False,
            allow_manual_captcha=False
        ) as bot:
            print("   ✅ 浏览器已启动")
            print("   访问 JobsDB 首页...")

            bot._page.goto("https://hk.jobsdb.com/", timeout=30000)
            print("   ✅ 页面加载成功")

            print("   等待 3 秒...")
            time.sleep(3)

        print("   ✅ 浏览器已自动关闭")
        return True

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_cleanup():
    """测试异常时的资源清理"""
    print("\n" + "=" * 50)
    print("测试: 异常时的资源清理")
    print("=" * 50)

    print("\n模拟启动过程中的错误...")
    try:
        bot = JobsDBApplyBot(headless=True)
        bot.start()

        # 模拟一个错误
        try:
            raise Exception("模拟的错误")
        except:
            bot.close()
            print("   ✅ 异常捕获后成功清理资源")

        return True

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False


if __name__ == "__main__":
    print("🧪 开始测试浏览器功能\n")
    print("⚠️ 注意: 这个测试会打开浏览器窗口，请不要关闭它\n")

    # 测试 1: 手动启动/关闭
    success1 = test_browser_lifecycle()

    # 测试 2: Context Manager
    success2 = test_context_manager()

    # 测试 3: 错误清理
    success3 = test_error_cleanup()

    # 总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"测试 1 (手动管理): {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"测试 2 (Context Manager): {'✅ 通过' if success2 else '❌ 失败'}")
    print(f"测试 3 (错误清理): {'✅ 通过' if success3 else '❌ 失败'}")

    if success1 and success2 and success3:
        print("\n🎉 所有测试通过！Playwright 工作正常。")
    else:
        print("\n⚠️ 部分测试失败。")
        print("\n可能的原因:")
        print("1. Playwright 未安装: 运行 'playwright install chromium'")
        print("2. 网络问题: 检查是否能访问 hk.jobsdb.com")
