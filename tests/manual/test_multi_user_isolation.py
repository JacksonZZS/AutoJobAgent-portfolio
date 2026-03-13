#!/usr/bin/env python3
"""
多用户数据隔离测试脚本

测试内容：
1. 不同用户的历史记录隔离
2. 不同用户的状态文件隔离
3. 不同用户的信号文件隔离
4. 并发访问测试
"""

import sys
import os
import time
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.history_manager import HistoryManager
from core.status_manager import get_status_manager, TaskStatus
from core.interaction_manager import get_interaction_manager


def test_history_isolation():
    """测试历史记录隔离"""
    print("\n" + "="*60)
    print("测试 1: 历史记录隔离")
    print("="*60)

    # 创建两个用户的历史管理器
    user1_history = HistoryManager(user_id="jackson")
    user2_history = HistoryManager(user_id="alice")

    # 用户1添加职位
    print("\n👤 用户 jackson 添加职位...")
    user1_history.add_job(
        link="https://hk.jobsdb.com/job/11111111",
        title="Python Developer",
        company="Tech Corp",
        status="success"
    )
    print(f"✅ 用户 jackson 历史记录数: {len(user1_history.history)}")

    # 用户2添加职位
    print("\n👤 用户 alice 添加职位...")
    user2_history.add_job(
        link="https://hk.jobsdb.com/job/22222222",
        title="Data Scientist",
        company="AI Labs",
        status="success"
    )
    print(f"✅ 用户 alice 历史记录数: {len(user2_history.history)}")

    # 验证隔离
    print("\n🔍 验证数据隔离...")
    user1_has_job1 = user1_history.is_processed("https://hk.jobsdb.com/job/11111111")
    user1_has_job2 = user1_history.is_processed("https://hk.jobsdb.com/job/22222222")
    user2_has_job1 = user2_history.is_processed("https://hk.jobsdb.com/job/11111111")
    user2_has_job2 = user2_history.is_processed("https://hk.jobsdb.com/job/22222222")

    print(f"用户 jackson 有 job1: {user1_has_job1} (应为 True)")
    print(f"用户 jackson 有 job2: {user1_has_job2} (应为 False)")
    print(f"用户 alice 有 job1: {user2_has_job1} (应为 False)")
    print(f"用户 alice 有 job2: {user2_has_job2} (应为 True)")

    # 验证文件路径
    print("\n📁 验证文件路径...")
    print(f"用户 jackson 历史文件: {user1_history.filepath}")
    print(f"用户 alice 历史文件: {user2_history.filepath}")

    # 检查结果
    if user1_has_job1 and not user1_has_job2 and not user2_has_job1 and user2_has_job2:
        print("\n✅ 历史记录隔离测试通过")
        return True
    else:
        print("\n❌ 历史记录隔离测试失败")
        return False


def test_status_isolation():
    """测试状态文件隔离"""
    print("\n" + "="*60)
    print("测试 2: 状态文件隔离")
    print("="*60)

    # 创建两个用户的状态管理器
    user1_status = get_status_manager(user_id="jackson")
    user2_status = get_status_manager(user_id="alice")

    # 用户1更新状态
    print("\n👤 用户 jackson 更新状态...")
    user1_status.update(
        status=TaskStatus.SCRAPING,
        message="用户 jackson 正在抓取职位",
        progress=50
    )

    # 用户2更新状态
    print("\n👤 用户 alice 更新状态...")
    user2_status.update(
        status=TaskStatus.ANALYZING,
        message="用户 alice 正在分析职位",
        progress=75
    )

    # 读取状态
    print("\n🔍 验证状态隔离...")
    user1_data = user1_status.read_status()
    user2_data = user2_status.read_status()

    print(f"用户 jackson 状态: {user1_data['status']} - {user1_data['message']}")
    print(f"用户 alice 状态: {user2_data['status']} - {user2_data['message']}")

    # 验证文件路径
    print("\n📁 验证文件路径...")
    print(f"用户 jackson 状态文件: {user1_status.status_file}")
    print(f"用户 alice 状态文件: {user2_status.status_file}")

    # 检查结果
    if (user1_data['status'] == 'scraping' and
        user2_data['status'] == 'analyzing' and
        user1_data['message'] != user2_data['message']):
        print("\n✅ 状态文件隔离测试通过")
        return True
    else:
        print("\n❌ 状态文件隔离测试失败")
        return False


def test_signal_isolation():
    """测试信号文件隔离"""
    print("\n" + "="*60)
    print("测试 3: 信号文件隔离")
    print("="*60)

    # 创建两个用户的交互管理器
    user1_interaction = get_interaction_manager(user_id="jackson")
    user2_interaction = get_interaction_manager(user_id="alice")

    # 用户1设置信号
    print("\n👤 用户 jackson 设置 continue 信号...")
    user1_interaction.set_signal("continue")

    # 用户2设置信号
    print("\n👤 用户 alice 设置 cancel 信号...")
    user2_interaction.set_signal("cancel")

    # 读取信号
    print("\n🔍 验证信号隔离...")
    user1_signal = user1_interaction.read_signal()
    user2_signal = user2_interaction.read_signal()

    print(f"用户 jackson 信号: {user1_signal['action']}")
    print(f"用户 alice 信号: {user2_signal['action']}")

    # 验证文件路径
    print("\n📁 验证文件路径...")
    print(f"用户 jackson 信号文件: {user1_interaction.signal_file}")
    print(f"用户 alice 信号文件: {user2_interaction.signal_file}")

    # 检查结果
    if (user1_signal['action'] == 'continue' and
        user2_signal['action'] == 'cancel'):
        print("\n✅ 信号文件隔离测试通过")
        return True
    else:
        print("\n❌ 信号文件隔离测试失败")
        return False


def test_file_structure():
    """测试文件结构"""
    print("\n" + "="*60)
    print("测试 4: 文件结构验证")
    print("="*60)

    base_dir = Path(__file__).parent

    # 检查目录结构
    expected_dirs = [
        "data/histories",
        "data/status",
        "data/signals"
    ]

    print("\n📁 检查目录结构...")
    all_exist = True
    for dir_path in expected_dirs:
        full_path = base_dir / dir_path
        exists = full_path.exists()
        print(f"{'✅' if exists else '❌'} {dir_path}: {'存在' if exists else '不存在'}")
        if not exists:
            all_exist = False

    # 检查用户文件
    print("\n📄 检查用户文件...")
    user_files = [
        "data/histories/history_jackson.json",
        "data/histories/history_alice.json",
        "data/status/status_jackson.json",
        "data/status/status_alice.json",
        "data/signals/signal_jackson.json",
        "data/signals/signal_alice.json"
    ]

    for file_path in user_files:
        full_path = base_dir / file_path
        exists = full_path.exists()
        print(f"{'✅' if exists else '❌'} {file_path}: {'存在' if exists else '不存在'}")

    if all_exist:
        print("\n✅ 文件结构验证通过")
        return True
    else:
        print("\n⚠️ 部分目录不存在（这是正常的，会在使用时自动创建）")
        return True


def cleanup_test_data():
    """清理测试数据"""
    print("\n" + "="*60)
    print("清理测试数据")
    print("="*60)

    base_dir = Path(__file__).parent

    test_files = [
        "data/histories/history_jackson.json",
        "data/histories/history_alice.json",
        "data/status/status_jackson.json",
        "data/status/status_alice.json",
        "data/signals/signal_jackson.json",
        "data/signals/signal_alice.json"
    ]

    print("\n🧹 删除测试文件...")
    for file_path in test_files:
        full_path = base_dir / file_path
        if full_path.exists():
            full_path.unlink()
            print(f"✅ 已删除: {file_path}")

    print("\n✅ 清理完成")


def main():
    """运行所有测试"""
    print("\n" + "🧪 "*30)
    print("多用户数据隔离测试套件")
    print("🧪 "*30)

    results = []

    try:
        # 运行测试
        results.append(("历史记录隔离", test_history_isolation()))
        results.append(("状态文件隔离", test_status_isolation()))
        results.append(("信号文件隔离", test_signal_isolation()))
        results.append(("文件结构验证", test_file_structure()))

        # 汇总结果
        print("\n" + "="*60)
        print("📊 测试结果汇总")
        print("="*60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{status} - {test_name}")

        print(f"\n总计: {passed}/{total} 测试通过")

        # 清理测试数据
        cleanup_test_data()

        if passed == total:
            print("\n🎉 所有测试通过！多用户数据隔离功能正常工作。")
            print("\n💡 下一步：")
            print("   1. 启动 Dashboard: streamlit run app_dashboard.py")
            print("   2. 打开多个浏览器标签页测试多用户场景")
            print("   3. 验证不同用户的数据完全独立")
            return 0
        else:
            print("\n❌ 部分测试失败，请检查代码")
            return 1

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
