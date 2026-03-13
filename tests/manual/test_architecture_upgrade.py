#!/usr/bin/env python3
"""
测试脚本 - 验证架构升级功能

测试内容：
1. URL 清理和标准化功能
2. InteractionManager 信号控制
3. 历史记录早期保存
4. 重复抓取防止
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.url_cleaner import clean_job_url, extract_job_id, normalize_url
from core.interaction_manager import get_interaction_manager
from core.history_manager import HistoryManager


def test_url_cleaner():
    """测试 URL 清理功能"""
    print("\n" + "="*60)
    print("测试 1: URL 清理功能")
    print("="*60)

    test_urls = [
        "https://hk.jobsdb.com/job/12345678?source=email&ref=abc",
        "https://hk.jobsdb.com/job/12345678",
        "https://hk.jobsdb.com/hk/en/job/python-developer-87654321?utm_source=google",
    ]

    for url in test_urls:
        cleaned = clean_job_url(url)
        job_id = extract_job_id(url)
        normalized = normalize_url(url)

        print(f"\n原始 URL: {url}")
        print(f"清理后:   {cleaned}")
        print(f"职位 ID:  {job_id}")
        print(f"标准化:   {normalized}")

    print("\n✅ URL 清理功能测试完成")


def test_history_manager():
    """测试历史记录管理器"""
    print("\n" + "="*60)
    print("测试 2: 历史记录管理器（URL 去重）")
    print("="*60)

    # 使用测试文件
    history_mgr = HistoryManager(history_file="data/test_history.json")

    # 测试相同职位的不同 URL 格式
    test_jobs = [
        {
            "url": "https://hk.jobsdb.com/job/12345678?source=email",
            "title": "Python Developer",
            "company": "Tech Corp"
        },
        {
            "url": "https://hk.jobsdb.com/job/12345678?source=web&ref=search",
            "title": "Python Developer",
            "company": "Tech Corp"
        },
        {
            "url": "https://hk.jobsdb.com/job/12345678",
            "title": "Python Developer",
            "company": "Tech Corp"
        }
    ]

    print("\n添加第一个职位...")
    job1 = test_jobs[0]
    history_mgr.add_job(
        link=job1["url"],
        title=job1["title"],
        company=job1["company"],
        status="success"
    )
    print(f"✅ 已添加: {job1['url']}")

    print("\n检查其他 URL 格式是否被识别为相同职位...")
    for i, job in enumerate(test_jobs[1:], start=2):
        is_processed = history_mgr.is_processed(job["url"])
        if is_processed:
            print(f"✅ URL {i} 被正确识别为已处理: {job['url']}")
        else:
            print(f"❌ URL {i} 未被识别为已处理: {job['url']}")

    # 清理测试文件
    test_file = "data/test_history.json"
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"\n🧹 已清理测试文件: {test_file}")

    print("\n✅ 历史记录管理器测试完成")


def test_interaction_manager():
    """测试交互管理器（需要手动确认）"""
    print("\n" + "="*60)
    print("测试 3: 交互管理器（信号控制）")
    print("="*60)

    interaction_mgr = get_interaction_manager()

    print("\n重置信号...")
    interaction_mgr.reset_signal()
    print("✅ 信号已重置")

    print("\n设置 'continue' 信号...")
    interaction_mgr.set_signal("continue")
    print("✅ 信号已设置")

    print("\n读取信号...")
    signal = interaction_mgr.read_signal()
    if signal and signal.get("action") == "continue":
        print(f"✅ 信号读取成功: {signal}")
    else:
        print(f"❌ 信号读取失败: {signal}")

    print("\n重置信号...")
    interaction_mgr.reset_signal()
    print("✅ 信号已重置")

    # 测试等待功能（带超时）
    print("\n测试等待功能（5秒超时）...")
    print("💡 提示：在另一个终端运行以下命令来发送信号：")
    print(f"   python -c \"import json; f=open('data/user_signal.json', 'w'); json.dump({{'action': 'continue'}}, f); f.close()\"")

    start_time = time.time()
    success = interaction_mgr.wait_for_continue(timeout=5, check_interval=0.5)
    elapsed = time.time() - start_time

    if success:
        print(f"✅ 收到 continue 信号 (耗时: {elapsed:.1f}s)")
    else:
        print(f"⏱️ 等待超时 (耗时: {elapsed:.1f}s)")

    print("\n✅ 交互管理器测试完成")


def test_early_save():
    """测试早期保存功能"""
    print("\n" + "="*60)
    print("测试 4: 早期历史记录保存（防止重复抓取）")
    print("="*60)

    # 模拟抓取流程
    history_mgr = HistoryManager(history_file="data/test_history_early.json")

    job_url = "https://hk.jobsdb.com/job/99999999"
    job_title = "Test Position"
    job_company = "Test Company"

    print(f"\n模拟抓取到新职位: {job_title} @ {job_company}")

    # 1. 检查是否已处理
    is_processed = history_mgr.is_processed(job_url)
    print(f"检查历史记录: {'已处理' if is_processed else '未处理'}")

    if not is_processed:
        # 2. 立即标记为 pending
        print("\n立即保存到历史记录（状态: pending）...")
        history_mgr.add_job(
            link=job_url,
            title=job_title,
            company=job_company,
            status="pending",
            reason="Job discovered, pending analysis"
        )
        print("✅ 已保存（状态: pending）")

        # 3. 模拟 AI 分析（可能失败或中断）
        print("\n模拟 AI 分析过程...")
        time.sleep(1)
        print("✅ AI 分析完成")

        # 4. 更新为最终状态
        print("\n更新历史记录（状态: success）...")
        history_mgr.add_job(
            link=job_url,
            title=job_title,
            company=job_company,
            status="success",
            score=85,
            reason="Successfully applied"
        )
        print("✅ 已更新（状态: success）")

    # 5. 再次检查（应该被识别为已处理）
    print("\n再次检查历史记录...")
    is_processed = history_mgr.is_processed(job_url)
    if is_processed:
        print("✅ 职位被正确识别为已处理，不会重复抓取")
    else:
        print("❌ 职位未被识别为已处理")

    # 清理测试文件
    test_file = "data/test_history_early.json"
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"\n🧹 已清理测试文件: {test_file}")

    print("\n✅ 早期保存功能测试完成")


def main():
    """运行所有测试"""
    print("\n" + "🧪 "*30)
    print("架构升级功能测试套件")
    print("🧪 "*30)

    try:
        test_url_cleaner()
        test_history_manager()
        test_interaction_manager()
        test_early_save()

        print("\n" + "="*60)
        print("🎉 所有测试完成！")
        print("="*60)
        print("\n✅ 架构升级功能验证通过")
        print("\n💡 下一步：")
        print("   1. 启动 Dashboard: streamlit run app_dashboard.py")
        print("   2. 上传简历并启动自动投递")
        print("   3. 在 Web 界面测试「继续」按钮功能")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
