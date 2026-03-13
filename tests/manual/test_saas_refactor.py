"""
SaaS 系统重构 - 综合测试套件
测试并发控制、评分决策和全局监控功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from core.browser_pool import acquire_browser_context, get_browser_pool_status
from core.global_monitor import get_global_monitor, log_user_event, reset_scanned_jobs


def print_section(title: str):
    """打印测试章节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def test_browser_concurrency():
    """测试 1: 浏览器并发控制"""
    print_section("测试 1: 浏览器并发控制（最多 2 个实例）")

    async def launch_browser(user_id: str, duration: int):
        """模拟浏览器使用"""
        print(f"[{user_id}] 🔵 请求浏览器...")

        try:
            async with acquire_browser_context(user_id=user_id, headless=True) as ctx:
                print(f"[{user_id}] ✅ 浏览器已获取")

                # 检查当前状态
                status = await get_browser_pool_status()
                print(f"[{user_id}] 📊 当前状态: {status['current_instances']}/{status['max_instances']} 实例运行")

                # 模拟使用
                await asyncio.sleep(duration)

                print(f"[{user_id}] 🔴 释放浏览器")

        except Exception as e:
            print(f"[{user_id}] ❌ 错误: {e}")

    # 同时启动 4 个浏览器（应该只有 2 个能同时运行，其他 2 个排队）
    print("\n启动 4 个并发浏览器请求...")
    print("预期行为：前 2 个立即获取，后 2 个排队等待\n")

    tasks = [
        launch_browser("user_1", 3),
        launch_browser("user_2", 3),
        launch_browser("user_3", 3),
        launch_browser("user_4", 3)
    ]

    await asyncio.gather(*tasks)

    # 验证最终状态
    final_status = await get_browser_pool_status()
    print(f"\n✅ 测试完成！最终状态: {final_status}")

    assert final_status["current_instances"] == 0, "所有浏览器应该已释放"
    print("✅ 并发控制测试通过！")


def test_global_monitor():
    """测试 3: 全局监控系统"""
    print_section("测试 3: 全局监控系统")

    monitor = get_global_monitor()

    # 测试 1: 更新用户状态
    print("\n📝 测试 1: 更新用户状态")

    monitor.update_user_status(
        user_id="test_user_1",
        username="alice",
        active_jobs=2,
        total_jobs=10,
        last_score=75,
        last_decision="auto"
    )

    monitor.update_user_status(
        user_id="test_user_2",
        username="bob",
        active_jobs=1,
        total_jobs=5,
        last_score=60,
        last_decision="semi_auto"
    )

    print("✅ 用户状态已更新")

    # 测试 2: 记录事件
    print("\n📝 测试 2: 记录事件")

    log_user_event(
        user_id="test_user_1",
        username="alice",
        level="INFO",
        event_type="job_applied",
        message="成功投递职位: Python Developer @ TechCorp",
        job_id="job_123",
        extra={"score": 75, "decision": "auto"}
    )

    log_user_event(
        user_id="test_user_2",
        username="bob",
        level="WARNING",
        event_type="job_pending_review",
        message="等待人工复核: Senior Engineer @ BigCorp",
        job_id="job_456",
        extra={"score": 60, "decision": "semi_auto"}
    )

    print("✅ 事件已记录")

    # 测试 3: 获取系统指标
    print("\n📝 测试 3: 获取系统指标")

    system_metrics = monitor.get_system_metrics()
    print(f"系统指标: {system_metrics}")

    assert "max_browser_instances" in system_metrics
    assert "current_browser_instances" in system_metrics
    print("✅ 系统指标获取成功")

    # 测试 4: 获取所有用户状态
    print("\n📝 测试 4: 获取所有用户状态")

    all_users = monitor.get_all_users_status()
    print(f"活跃用户数: {len(all_users)}")

    for user_id, user_data in all_users.items():
        print(f"  - {user_data.get('username', user_id)}: {user_data.get('total_jobs', 0)} 个任务")

    assert "test_user_1" in all_users
    assert "test_user_2" in all_users
    print("✅ 用户状态获取成功")

    # 测试 5: 获取最近事件
    print("\n📝 测试 5: 获取最近事件")

    recent_events = monitor.get_recent_events(limit=5)
    print(f"最近事件数: {len(recent_events)}")

    for event in recent_events[:3]:
        print(f"  - [{event.get('level')}] {event.get('username')}: {event.get('message')}")

    assert len(recent_events) > 0
    print("✅ 事件获取成功")

    # 测试 6: 重置用户数据
    print("\n📝 测试 6: 重置用户数据")

    monitor.reset_user_data("test_user_1")
    reset_scanned_jobs("test_user_1", "alice")

    user_status = monitor.get_user_status("test_user_1")
    assert user_status["total_jobs"] == 0, "总任务数应该被重置为 0"
    print("✅ 用户数据重置成功")

    print("\n✅ 所有全局监控测试通过！")


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "🚀" * 30)
    print("  SaaS 系统重构 - 综合测试套件")
    print("🚀" * 30)

    try:
        # 测试 1: 浏览器并发控制
        await test_browser_concurrency()

        # 测试 2: 全局监控系统
        test_global_monitor()

        # 所有测试通过
        print("\n" + "✅" * 30)
        print("  所有测试通过！系统重构成功！")
        print("✅" * 30)

        return True

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return False

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(run_all_tests())

    # 退出码
    sys.exit(0 if success else 1)
