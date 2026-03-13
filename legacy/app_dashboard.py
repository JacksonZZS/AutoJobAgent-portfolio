import streamlit as st
import os
import uuid
import json
import subprocess
import sys
import time
import hashlib
import logging
from pathlib import Path

# 配置 logger
logger = logging.getLogger(__name__)

# 🔴 导入认证模块
from core.auth_ui import render_auth_page, render_user_info_sidebar, check_authentication

# 尝试导入 LLM 引擎
try:
    from core.llm_engine import LLMEngine
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

# 导入状态管理器
try:
    from core.status_manager import get_status_manager, TaskStatus
    HAS_STATUS_MANAGER = True
except ImportError:
    HAS_STATUS_MANAGER = False

# 导入交互管理器
try:
    from core.interaction_manager import get_interaction_manager
    HAS_INTERACTION_MANAGER = True
except ImportError:
    HAS_INTERACTION_MANAGER = False

# 🔴 导入远程物料中心
try:
    from dashboard.remote_asset_center import remote_asset_center_fragment
    HAS_REMOTE_ASSET_CENTER = True
except ImportError:
    HAS_REMOTE_ASSET_CENTER = False

# 🔴 导入投递历史组件
try:
    from dashboard.job_history import job_history_fragment
    HAS_JOB_HISTORY = True
except ImportError:
    HAS_JOB_HISTORY = False

# 🔴 导入 Profile 编辑器
try:
    from dashboard.profile_editor import render_profile_editor
    HAS_PROFILE_EDITOR = True
except ImportError:
    HAS_PROFILE_EDITOR = False

# ================= 配置区 =================
st.set_page_config(
    page_title="AutoJobAgent Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔴 上传目录将在用户登录后动态创建
# UPLOAD_DIR 将根据 user_id 动态设置

CACHE_FILE = Path("data/analysis_cache.json")
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

# 🔴 新增：状态超时阈值（秒）
STATUS_TIMEOUT_SECONDS = 150  # 增加到100秒，适应较慢的网络环境


def reset_run_state():
    """清空所有以 aj_ 开头的运行状态和职位缓存"""
    keys_to_remove = [key for key in st.session_state.keys() if key.startswith("aj_")]
    for key in keys_to_remove:
        del st.session_state[key]

    # 同时清空职位和公司缓存
    cache_keys = ["current_job", "current_company", "job_list", "applied_jobs"]
    for key in cache_keys:
        if key in st.session_state:
            del st.session_state[key]


def check_status_expired(status: dict, timeout_seconds: int = STATUS_TIMEOUT_SECONDS) -> bool:
    """检查状态是否过期（超过指定秒数未更新）"""
    last_updated = status.get("last_updated")
    if not last_updated:
        return False

    try:
        from datetime import datetime
        # 解析时间戳
        if isinstance(last_updated, str):
            last_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        else:
            last_time = datetime.fromtimestamp(last_updated)

        # 计算时间差
        now = datetime.now()
        if last_time.tzinfo:
            from datetime import timezone
            now = datetime.now(timezone.utc)

        elapsed = (now - last_time).total_seconds()
        return elapsed > timeout_seconds
    except (ValueError, TypeError):
        return False


def get_user_upload_dir(user_id) -> Path:
    """
    获取用户专属的上传目录

    Args:
        user_id: 用户 ID

    Returns:
        用户上传目录路径
    """
    upload_dir = Path(f"data/uploads/{user_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir

# ================= 缓存管理函数 =================
def calculate_file_hash(file_bytes, user_id: str = None):
    """
    计算文件的 MD5 哈希值（包含 user_id）

    Args:
        file_bytes: 文件字节
        user_id: 用户 ID（确保不同用户拥有独立缓存）

    Returns:
        哈希值
    """
    hasher = hashlib.md5()
    hasher.update(file_bytes)

    # 🔴 包含 user_id 确保跨用户隔离
    if user_id:
        hasher.update(user_id.encode('utf-8'))

    return hasher.hexdigest()

def load_cache():
    """加载缓存数据"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载缓存失败: {e}")
            return {}
    return {}

def save_cache(cache_data):
    """保存缓存数据"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存缓存失败: {e}")

def get_cached_analysis(cache_key: str):
    """
    根据缓存键获取缓存的分析结果

    Args:
        cache_key: 缓存键（file_hash + user_id）

    Returns:
        缓存数据或 None
    """
    cache = load_cache()
    return cache.get(cache_key)

def save_analysis_to_cache(cache_key: str, analysis_data: dict):
    """
    保存分析结果到缓存

    Args:
        cache_key: 缓存键（file_hash + user_id）
        analysis_data: 分析数据
    """
    cache = load_cache()
    cache[cache_key] = {
        "keywords": analysis_data.get("keywords", ""),
        "blocked_companies": analysis_data.get("blocked_companies", ""),
        "title_exclusions": analysis_data.get("title_exclusions", ""),
        "timestamp": time.time()
    }
    save_cache(cache)


# ================= 1. 认证检查（移除旧的密码门锁）=================
# 旧的 check_password() 函数已被认证系统替代

# ================= 2. 核心逻辑 =================
def init_session():
    """初始化 Session 状态（支持多用户数据隔离）"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]

    # 🔴 新增：使用真实的用户 ID（来自认证系统）
    if "user_id" not in st.session_state:
        # 如果已认证，使用数据库中的用户 ID
        if check_authentication():
            # user_id 已在认证时设置
            pass
        else:
            # 未认证，使用临时 ID（不应该到达这里）
            st.session_state.user_id = f"guest_{st.session_state.session_id}"

    if "resume_path" not in st.session_state:
        st.session_state.resume_path = None

    if "resume_hash" not in st.session_state:
        st.session_state.resume_hash = None

    if "transcript_path" not in st.session_state:
        st.session_state.transcript_path = None

    if "limit" not in st.session_state:
        st.session_state.limit = 1  # 默认值设为 1，方便快速测试

    # 初始化输入框的绑定变量 (如果没有值则为空字符串)
    if "ui_keywords" not in st.session_state:
        st.session_state.ui_keywords = ""
    if "ui_block_list" not in st.session_state:
        st.session_state.ui_block_list = ""
    if "ui_title_exclusions" not in st.session_state:
        st.session_state.ui_title_exclusions = ""

    # 🔴 [关键修复] 初始化自动刷新开关（确保在渲染 checkbox 之前初始化）
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = True

def analyze_resume(file_path, cache_key):
    """
    调用 LLM 分析简历并强制更新 UI

    Args:
        file_path: 简历文件路径
        cache_key: 缓存键（包含 user_id）
    """
    if not HAS_LLM:
        st.error("⚠️ 未检测到 LLM 引擎，无法智能分析。")
        return

    try:
        llm = LLMEngine()

        with st.spinner("🤖 AI 正在深度分析简历...提取技能、识别前雇主、判断资历..."):
            # 构造 Prompt
            prompt = """
            Analyze the resume and return a strict JSON object (no markdown).
            Fields required:
            1. "keywords": 3-5 best job search keywords (comma separated).
            2. "blocked_companies": List ALL company names found in Work History (comma separated).
            3. "title_exclusions":
               - If candidate is Fresh Grad/Junior (0-3 yrs): Return "Senior, Manager, Director, Lead, Principal, VP, Head, Chief".
               - If candidate is Senior (5+ yrs): Return "Intern, Trainee, Junior, Assistant".

            JSON Example:
            {
                "keywords": "Python, Data Analysis",
                "blocked_companies": "Tencent, Alibaba",
                "title_exclusions": "Manager, Director"
            }
            """

            # 读取 PDF 文本 (简化版)
            import PyPDF2
            text_content = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_content += page.extract_text()

            # 调用 LLM - 使用 _call_ai 方法
            system_prompt = "You are a resume analysis expert. Output strictly valid JSON only, no markdown."
            user_prompt = f"{prompt}\n\nRESUME CONTENT:\n{text_content[:4000]}"

            data = llm._call_ai(system_prompt, user_prompt, max_tokens=1000, prefill="{")

            # 检查是否成功获取数据
            if data is None:
                st.error("❌ LLM 返回了无效的响应，请重试")
                return

            # 调试：显示解析后的数据
            with st.expander("🔍 调试信息（点击展开）"):
                st.write("**解析后的数据:**")
                st.json(data)

            # 关键修复：直接更新绑定了 key 的 session_state
            # 这样 Streamlit 会在 rerun 后自动把值填入输入框
            st.session_state.ui_keywords = data.get("keywords", "")
            st.session_state.ui_block_list = data.get("blocked_companies", "")
            st.session_state.ui_title_exclusions = data.get("title_exclusions", "")

            # ✅ 保存到缓存（使用 cache_key）
            save_analysis_to_cache(cache_key, data)

            # 调试：确认 Session State 已更新
            with st.expander("🔍 调试信息（点击展开）"):
                st.write("**Session State 已更新:**")
                st.write(f"- ui_keywords: `{st.session_state.ui_keywords}`")
                st.write(f"- ui_block_list: `{st.session_state.ui_block_list}`")
                st.write(f"- ui_title_exclusions: `{st.session_state.ui_title_exclusions}`")

            st.toast("✅ 分析成功！已自动填充表单。", icon="🎉")
            time.sleep(1)
            st.rerun()  # 强制刷新界面显示新值

    except Exception as e:
        st.error(f"❌ 分析失败: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

# ================= 3. 界面渲染 =================
def main():
    # 🔴 认证检查（必须在最前面）
    if not check_authentication():
        # 显示登录/注册页面
        render_auth_page()
        return

    # 已认证，继续正常流程
    init_session()

    # 🔴 [新增] Dashboard 启动时自动清理过期的终止状态
    if HAS_STATUS_MANAGER:
        status_mgr = get_status_manager(user_id=st.session_state.user_id)
        current_status = status_mgr.read_status()
        status_value = current_status.get("status", "idle")

        # 检查状态是否过期
        last_updated = current_status.get("last_updated", "")
        needs_refresh = False

        if last_updated:
            try:
                from datetime import datetime
                update_time = datetime.fromisoformat(last_updated)
                time_diff = (datetime.now() - update_time).total_seconds()

                # 情况1：completed/error/stopped 状态超过30秒，重置为 idle
                if status_value in ["completed", "error", "stopped"] and time_diff > 30:
                    status_mgr.reset()
                    st.toast(f"🧹 已清理旧任务状态（{int(time_diff)}秒前）", icon="🧹")
                    logger.info(f"🧹 Dashboard 启动时清理了过期的 {status_value} 状态（{time_diff:.1f}秒前）")
                    needs_refresh = True

                # 情况2：idle 状态超过10分钟，刷新时间戳
                elif status_value == "idle" and time_diff > 600:  # 10分钟
                    status_mgr.update(
                        status="idle",
                        message="系统就绪",
                        progress=0,
                        step=""
                    )
                    logger.info(f"🔄 刷新了过期的 idle 状态时间戳（{time_diff:.1f}秒前）")
                    needs_refresh = True

                # 情况3：其他状态超过5分钟，视为异常，重置
                elif status_value not in ["idle", "completed", "error", "stopped"] and time_diff > 300:  # 5分钟
                    status_mgr.reset()
                    st.warning(f"⚠️ 检测到异常状态（{status_value}，{int(time_diff)}秒前），已自动重置")
                    logger.warning(f"⚠️ 清理异常状态：{status_value}（{time_diff:.1f}秒前）")
                    needs_refresh = True

                if needs_refresh:
                    time.sleep(0.5)
                    st.rerun()

            except Exception as e:
                logger.warning(f"⚠️ 清理过期状态失败: {e}")

    st.title("🤖 AutoJobAgent 控制台（SaaS 多用户版）")
    st.caption(f"🆔 Session: {st.session_state.session_id} | 👤 User: {st.session_state.username} (ID: {st.session_state.user_id})")

    # 🔴 [新增] 显示注册成功欢迎消息
    if st.session_state.get("just_registered"):
        st.success("🎉 注册成功！欢迎使用 AutoJobAgent！")
        st.balloons()
        # 清除标志，避免重复显示
        del st.session_state.just_registered

    # 🔴 新增：顶部任务状态指示器
    if HAS_STATUS_MANAGER:
        status_mgr = get_status_manager(user_id=st.session_state.user_id)
        current_status = status_mgr.read_status()
        status_value = current_status.get("status", "idle")

        # 根据状态显示不同的横幅
        if status_value in ["scraping", "analyzing", "generating", "applying"]:
            st.info(f"🔄 任务进行中: {current_status.get('message', '处理中...')}", icon="⚙️")
        elif status_value == "waiting_user":
            st.warning("⚠️ 需要您的操作！请查看下方监控区域", icon="🛑")
        elif status_value == "completed":
            st.success("✅ 任务已完成！", icon="🎉")
        elif status_value == "error":
            st.error(f"❌ 任务出错: {current_status.get('message', '未知错误')}", icon="⚠️")

    # --- 侧边栏 ---
    with st.sidebar:
        # 🔴 显示用户信息和退出按钮
        render_user_info_sidebar()

        st.header("📂 1. 上传材料")

        # 简历上传
        uploaded_resume = st.file_uploader("请上传 PDF 简历", type=["pdf"], key="resume_uploader")

        if uploaded_resume:
            # 🔴 使用用户专属目录
            user_upload_dir = get_user_upload_dir(st.session_state.user_id)
            file_name = f"{st.session_state.username}_resume.pdf"
            save_path = user_upload_dir / file_name

            # 读取文件内容并计算哈希（包含 user_id）
            file_bytes = uploaded_resume.getbuffer()
            file_hash = calculate_file_hash(file_bytes, user_id=str(st.session_state.user_id))

            # 保存文件
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            st.session_state.resume_path = str(save_path.absolute())
            st.session_state.resume_hash = file_hash
            st.success("✅ 简历已上传")

            # ✅ Cache-First Strategy: 立即检查缓存（使用包含 user_id 的 cache_key）
            cached_data = get_cached_analysis(file_hash)
            if cached_data:
                # 命中缓存 - 自动填充
                st.session_state.ui_keywords = cached_data.get("keywords", "")
                st.session_state.ui_block_list = cached_data.get("blocked_companies", "")
                st.session_state.ui_title_exclusions = cached_data.get("title_exclusions", "")

                st.toast("⚡️ 检测到已有记录，已秒速加载历史分析结果！", icon="⚡")
                st.info("💡 已从缓存加载历史分析结果")

                # 显示缓存信息
                with st.expander("📦 缓存信息"):
                    st.write(f"**文件哈希:** `{file_hash[:16]}...`")
                    st.write(f"**缓存时间:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cached_data.get('timestamp', 0)))}")
                    st.json(cached_data)
            else:
                st.info("💡 这是新简历，请点击下方「开始分析简历」按钮")
        else:
            st.session_state.resume_path = None
            st.session_state.resume_hash = None

        # 成绩单上传（可选）
        uploaded_transcript = st.file_uploader(
            "上传成绩单 (可选)",
            type=["pdf"],
            key="transcript_uploader",
            help="成绩单可以帮助 AI 更好地分析你的学历背景"
        )

        if uploaded_transcript:
            # 🔴 使用用户专属目录
            user_upload_dir = get_user_upload_dir(st.session_state.user_id)
            file_name = f"{st.session_state.username}_transcript.pdf"
            save_path = user_upload_dir / file_name
            with open(save_path, "wb") as f:
                f.write(uploaded_transcript.getbuffer())

            st.session_state.transcript_path = str(save_path.absolute())
            st.success("✅ 成绩单已上传")
        else:
            st.session_state.transcript_path = None

        st.divider()
        st.header("🧠 2. 智能填充")
        if st.button("开始分析简历", type="primary", use_container_width=True):
            if st.session_state.resume_path and st.session_state.resume_hash:
                # 🔴 传递 cache_key（已包含 user_id）
                analyze_resume(st.session_state.resume_path, st.session_state.resume_hash)
            else:
                st.error("请先上传简历")

        st.divider()
        st.header("🛠️ 调试工具")

        # 🔴 新增：结束当前任务按钮
        if st.button("🛑 结束当前任务", type="secondary", use_container_width=True, help="安全终止正在运行的任务进程"):
            # 检查是否有正在运行的任务
            if "pid" in st.session_state and st.session_state.pid:
                try:
                    import signal
                    pid = st.session_state.pid

                    # 尝试优雅地终止进程
                    try:
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(2)  # 等待进程响应

                        # 检查进程是否还在运行
                        try:
                            os.kill(pid, 0)  # 检查进程是否存在
                            # 如果还在运行，强制终止
                            os.kill(pid, signal.SIGKILL)
                            st.warning(f"⚠️ 进程 {pid} 未响应 SIGTERM，已强制终止")
                        except OSError:
                            # 进程已经终止
                            pass
                    except OSError as e:
                        if e.errno == 3:  # No such process
                            st.info("ℹ️ 进程已经结束")
                        else:
                            raise

                    # 重置状态
                    if HAS_STATUS_MANAGER:
                        status_mgr = get_status_manager(user_id=st.session_state.user_id)
                        status_mgr.update(
                            status="stopped",
                            message="任务已被用户手动终止",
                            progress=0,
                            step="stopped"
                        )

                    # 清除 PID
                    del st.session_state.pid

                    st.toast("✅ 任务已终止", icon="🛑")
                    st.success("✅ 任务已成功终止")
                    time.sleep(1)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ 终止任务失败: {e}")
                    st.toast(f"❌ 终止失败: {e}", icon="❌")
            else:
                st.info("ℹ️ 当前没有正在运行的任务")
                st.toast("ℹ️ 没有运行中的任务", icon="🤷")

        # 清除历史记录按钮（添加二次确认）
        if "confirm_clear_history" not in st.session_state:
            st.session_state.confirm_clear_history = False

        if st.button("🧹 清空已投递历史", type="secondary", use_container_width=True, help="⚠️ 危险操作：会永久删除所有投递记录，无法恢复！"):
            st.session_state.confirm_clear_history = True

        # 二次确认对话框
        if st.session_state.confirm_clear_history:
            st.warning("⚠️ **确认清空历史记录？**")
            st.markdown("""
            **这将永久删除：**
            - ❌ 所有投递记录（职位、公司、时间）
            - ❌ 历史简历和求职信下载链接
            - ❌ 投递统计数据

            **此操作无法撤销！**
            """)

            col_confirm1, col_confirm2 = st.columns(2)

            with col_confirm1:
                if st.button("✅ 确认清空", type="primary", use_container_width=True, key="confirm_yes"):
                    # 🔴 使用用户专属的历史文件
                    history_path = f"data/histories/history_{st.session_state.user_id}.json"
                    job_history_path = "data/job_history.json"  # 旧的全局历史文件

                    deleted_count = 0
                    try:
                        # 删除用户专属历史
                        if os.path.exists(history_path):
                            os.remove(history_path)
                            deleted_count += 1
                            st.toast(f"✅ 已清除用户历史: {history_path}", icon="🗑️")

                        # 删除旧的全局历史（向后兼容）
                        if os.path.exists(job_history_path):
                            os.remove(job_history_path)
                            deleted_count += 1
                            st.toast(f"✅ 已清除全局历史: {job_history_path}", icon="🗑️")

                        if deleted_count > 0:
                            st.success(f"✅ 已清除 {deleted_count} 个历史记录文件")
                        else:
                            st.info("ℹ️ 暂无历史记录")
                            st.toast("⚠️ 暂无历史记录", icon="🤷")

                        # 重置确认状态
                        st.session_state.confirm_clear_history = False
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ 清除失败: {e}")
                        st.toast(f"❌ 清除失败: {e}", icon="❌")

            with col_confirm2:
                if st.button("❌ 取消", use_container_width=True, key="confirm_no"):
                    st.session_state.confirm_clear_history = False
                    st.rerun()

        # 🔴 新增：重置搜索记忆按钮
        if st.button("🔄 重置搜索记忆", type="secondary", use_container_width=True, help="清除已扫描职位缓存，允许重新搜索相同职位"):
            scanned_jobs_path = f"data/scanned_jobs_{st.session_state.user_id}.json"

            try:
                if os.path.exists(scanned_jobs_path):
                    os.remove(scanned_jobs_path)
                    st.success(f"✅ 已清除搜索记忆: {scanned_jobs_path}")
                    st.toast("✅ 搜索记忆已重置", icon="🔄")
                else:
                    st.info("ℹ️ 暂无搜索记忆")
                    st.toast("⚠️ 暂无搜索记忆", icon="🤷")
            except Exception as e:
                st.error(f"❌ 重置失败: {e}")
                st.toast(f"❌ 重置失败: {e}", icon="❌")

    # 🔴 [已删除] Dashboard 顶部的提示框按钮（现在统一使用远程物料中心的按钮）
    # 保留 lock_file 清理逻辑，但删除 UI 提示和按钮

    # 🔴 新增：UI 交互信号检测
    lock_file = Path(f"data/locks/user_interaction_{st.session_state.user_id}.lock")

    # 🔴 [新增] Dashboard 启动时清理旧的 lock_file
    if "lock_file_cleaned" not in st.session_state:
        if lock_file.exists():
            try:
                # 检查文件是否过期（超过5分钟）
                import os
                from datetime import datetime
                mtime = os.path.getmtime(lock_file)
                file_time = datetime.fromtimestamp(mtime)
                time_diff = (datetime.now() - file_time).total_seconds()

                if time_diff > 300:  # 5分钟
                    lock_file.unlink()
                    st.toast("🧹 已清理过期的交互锁文件", icon="🧹")
                    logger.info(f"🧹 Dashboard 启动时清理了过期的 lock_file（{time_diff:.1f}秒前）")
            except Exception as e:
                logger.warning(f"⚠️ 清理 lock_file 失败: {e}")

        st.session_state.lock_file_cleaned = True


    # --- 主界面 ---
    st.subheader("🛠️ 3. 投递配置 (可手动修改)")

    # 投递数量限制
    limit = st.number_input(
        "🎯 每次投递上限 (Limit)",
        min_value=0,
        max_value=100,
        value=st.session_state.limit,
        step=1,
        help="设置本次最多投递的职位数量。0 表示不限量。建议设为 1-5 进行快速测试。"
    )
    st.session_state.limit = limit

    # 添加黑名单开关
    use_blocklist = st.checkbox("启用公司黑名单过滤", value=False, help="取消勾选则不使用黑名单功能")

    col1, col2 = st.columns(2)

    with col1:
        # 注意：这里使用了 key 参数，直接绑定 session_state
        keywords = st.text_input(
            "🔎 职位搜索关键词",
            key="ui_keywords",
            placeholder="例如: Data Scientist"
        )

        title_exclusions = st.text_area(
            "🚫 职位排除词 (不投这些)",
            key="ui_title_exclusions",
            placeholder="例如: Manager, Senior, Director",
            help="AI 会根据你的资历自动生成，避免瞎投"
        )

    with col2:
        block_list = st.text_area(
            "🛡️ 公司黑名单 (不投这些)",
            key="ui_block_list",
            placeholder="例如: 前东家公司名",
            help="AI 会自动从你的简历里提取前雇主",
            disabled=not use_blocklist  # 如果未启用黑名单，则禁用输入框
        )

    # --- 启动 ---
    st.divider()
    st.write("### 🚀 4. 执行任务")
    
    if st.button("启动自动投递机器人", type="primary", use_container_width=True):
        if not st.session_state.resume_path:
            st.error("请先在左侧上传简历！")
        elif not keywords:
            st.error("关键词不能为空！")
        else:
            # 根据开关决定是否传递黑名单
            final_block_list = block_list if use_blocklist else ""

            # 🔴 使用真正的自动化脚本（传递 user_id）
            cmd = [
                sys.executable, "run_auto_apply.py",
                "--user_id", str(st.session_state.user_id),  # 🔴 修复：转换为字符串
                "--resume_path", st.session_state.resume_path,
                "--keywords", keywords,
                "--block_list", final_block_list,
                "--title_exclusions", title_exclusions,
                "--limit", str(limit if limit and limit > 0 else 10),
                "--headless", "true",
                "--delay", "5.0",
                "--page_size", "200"  # 🔴 [修复] 提高到200，抓取整页职位
            ]

            # 如果有成绩单，添加成绩单路径参数
            if st.session_state.transcript_path:
                cmd.extend(["--transcript_path", st.session_state.transcript_path])

            st.info("🚀 正在启动目标驱动的自动投递流程...")
            st.markdown("""
            **新版流式投递逻辑：**
            1. 🎯 目标驱动循环：只有达到目标投递数才停止
            2. 🔄 智能翻页：自动翻页抓取更多职位
            3. ⚡ 流式处理：抓取1个 → 评分 → 投递，无需等待批量处理
            4. 🧠 AI 决策透明：实时显示拒绝理由
            5. 🗑️ 历史去重：已投递的职位自动跳过
            """)

            # 显示配置信息
            with st.expander("📋 查看配置信息"):
                st.write(f"**简历路径:** {st.session_state.resume_path}")
                if st.session_state.transcript_path:
                    st.write(f"**成绩单路径:** {st.session_state.transcript_path}")
                else:
                    st.write(f"**成绩单路径:** 未上传")
                st.write(f"**目标投递数:** {limit if limit and limit > 0 else 10}")
                st.write(f"**关键词:** {keywords}")
                st.write(f"**黑名单:** {final_block_list if final_block_list else '无'}")
                st.write(f"**排除词:** {title_exclusions if title_exclusions else '无'}")
                st.write(f"**每页抓取:** 200 个")
                st.write(f"**投递延迟:** 5.0 秒")

            # Run from the repository root instead of a machine-specific absolute path.
            repo_root = Path(__file__).resolve().parents[1]
            process = subprocess.Popen(cmd, cwd=str(repo_root))
            st.session_state.pid = process.pid

            st.success(f"✅ 已启动自动化流程! PID: {process.pid}")
            st.markdown("👉 **请查看终端输出和弹出的 Chrome 窗口**")
            st.info("💡 提示：首次运行需要手动登录 JobsDB，之后会自动保存登录状态")
            st.warning("⚠️ 新版本使用流式处理，可能需要较长时间才能达到目标投递数")

            # 🔴 [关键修复] 启动后立即刷新页面，进入自动刷新循环
            st.toast("🔄 正在进入监控模式...", icon="🚀")
            time.sleep(1)
            st.rerun()

    # ===== 实时进度显示区域 =====
    st.divider()
    st.write("### 📊 5. 实时进度监控")

    if HAS_STATUS_MANAGER:
        # 🔴 新增：自动重载逻辑（基于文件监控）
        # 每 2 秒检查状态文件是否更新，如果更新则自动刷新页面
        status_mgr = get_status_manager(user_id=st.session_state.user_id)
        status_file_path = status_mgr.status_file

        # 初始化上次更新时间
        if "last_status_timestamp" not in st.session_state:
            st.session_state.last_status_timestamp = None

        # 🔴 关键改进：在自动刷新循环开始时加载状态
        current_status = status_mgr.read_status()
        current_timestamp = current_status.get("last_updated")
        status_value = current_status.get("status", "idle")

        # 🔴 检测到 idle 或 completed 时清空缓存
        if status_value in ["idle", "completed"]:
            reset_run_state()

        # 🔴 过期检测：超过60秒未更新则标记为连接断开
        is_expired = check_status_expired(current_status, timeout_seconds=STATUS_TIMEOUT_SECONDS)
        if is_expired and status_value not in ["idle", "completed", "error", "stopped"]:
            st.error(f"⚠️ 连接断开 - 状态超过 {STATUS_TIMEOUT_SECONDS} 秒未更新")
            status_value = "disconnected"

        # 🔴 [新增] 如果状态过期且不是终止状态，自动重置为 idle
        if is_expired and status_value not in ["idle", "completed", "error", "stopped"]:
            logger.warning(f"⚠️ 检测到过期状态（{STATUS_TIMEOUT_SECONDS}秒未更新），自动重置...")
            status_mgr.reset()
            st.warning(f"⚠️ 检测到过期状态，已自动重置。请重新启动任务。")
            time.sleep(1)
            st.rerun()

        # 🔴 智能刷新：只在状态真正变化时更新 UI
        # 初始化状态容器和缓存
        if "status_display_container" not in st.session_state:
            st.session_state.status_display_container = st.empty()

        if "last_status_cache" not in st.session_state:
            st.session_state.last_status_cache = {}

        # 检查状态是否变化
        status_changed = (
            current_timestamp != st.session_state.last_status_cache.get("timestamp") or
            status_value != st.session_state.last_status_cache.get("status") or
            current_status.get("current_job") != st.session_state.last_status_cache.get("current_job")
        )

        # 只在状态变化时更新容器
        if status_changed or not st.session_state.last_status_cache:
            # 更新缓存
            st.session_state.last_status_cache = {
                "timestamp": current_timestamp,
                "status": status_value,
                "current_job": current_status.get("current_job")
            }

            # 更新时间戳（用于旧的刷新逻辑）
            st.session_state.last_status_timestamp = current_timestamp

        # 添加自动刷新开关
        col_refresh1, col_refresh2 = st.columns([3, 1])
        with col_refresh1:
            auto_refresh = st.checkbox("启用自动刷新 (每2秒检测)", value=True, key="auto_refresh", help="自动检测状态文件变化并刷新页面")
        with col_refresh2:
            if st.button("🔄 立即刷新", use_container_width=True):
                # 清空缓存强制刷新
                st.session_state.last_status_cache = {}
                st.rerun()

        # 状态映射
        status_emoji_map = {
            "idle": "⚪",
            "initializing": "🔄",
            "scraping": "🕷️",
            "analyzing": "🤖",
            "generating": "📝",
            "applying": "🚀",
            "waiting_user": "⚠️",
            "completed": "✅",
            "error": "❌",
            "stopped": "🛑"
        }

        status_color_map = {
            "idle": "gray",
            "initializing": "blue",
            "scraping": "blue",
            "analyzing": "orange",
            "generating": "orange",
            "applying": "green",
            "waiting_user": "red",
            "completed": "green",
            "error": "red",
            "stopped": "gray"
        }

        status_value = current_status.get("status", "idle")
        status_emoji = status_emoji_map.get(status_value, "❓")
        message = current_status.get("message", "系统就绪")
        progress = current_status.get("progress", 0)
        current_job = current_status.get("current_job")
        stats = current_status.get("stats", {})

        # 显示当前状态
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.metric("当前状态", f"{status_emoji} {message}")

        with col2:
            st.metric("进度", f"{progress}%")

        with col3:
            last_updated = current_status.get("last_updated", "N/A")
            if last_updated != "N/A":
                try:
                    from datetime import datetime
                    update_time = datetime.fromisoformat(last_updated)
                    time_diff = (datetime.now() - update_time).total_seconds()
                    if time_diff < 60:
                        time_str = f"{int(time_diff)}秒前"
                    else:
                        time_str = f"{int(time_diff/60)}分钟前"
                    st.metric("更新时间", time_str)
                except:
                    st.metric("更新时间", "未知")
            else:
                st.metric("更新时间", "N/A")

        # 进度条
        if progress > 0:
            st.progress(progress / 100.0)

        # 当前处理的职位
        if current_job:
            with st.expander("📋 当前处理职位", expanded=True):
                job_title = current_job.get('title', 'N/A')
                job_company = current_job.get('company', 'N/A')
                job_score = current_job.get('score', 0)

                st.write(f"**职位**: {job_title}")
                st.write(f"**公司**: {job_company}")

                # 🔴 色彩语义：AI 分数显示
                if job_score > 0:
                    if job_score >= 80:
                        st.success(f"🟢 AI 匹配度: {job_score}/100 (优秀)")
                    elif job_score >= 60:
                        st.warning(f"🟡 AI 匹配度: {job_score}/100 (良好)")
                    else:
                        st.info(f"⚪ AI 匹配度: {job_score}/100 (一般)")

        # 🔴 透明度：使用 st.status() 实时展示后台日志流
        if status_value in ["scraping", "analyzing", "generating", "applying"]:
            status_labels = {
                "scraping": "🔍 抓取职位中",
                "analyzing": "⚖️ AI 评分中",
                "generating": "📝 生成简历中",
                "applying": "🚀 投递中"
            }
            with st.status(status_labels.get(status_value, "处理中..."), expanded=True):
                st.write(message)
                if current_job:
                    st.write(f"职位: {current_job.get('title', 'N/A')}")
                    st.write(f"公司: {current_job.get('company', 'N/A')}")

        # 🔴 新增：使用 st.empty() 动态更新日志流（防止累加）
        st.write("#### 📝 执行日志")

        # 创建日志占位符
        if "log_placeholder" not in st.session_state:
            st.session_state.log_placeholder = st.empty()

        # 获取最近的日志（最多显示最近50条）
        logs = current_status.get("logs", [])
        if isinstance(logs, list) and logs:
            # 只显示最近50条日志
            recent_logs = logs[-50:]
            log_text = "\n".join(recent_logs)

            # 使用占位符动态更新，而不是累加组件
            with st.session_state.log_placeholder.container():
                st.code(log_text, language="text")
        else:
            with st.session_state.log_placeholder.container():
                st.info("暂无日志输出")

        # ⚠️ 特别警告：等待用户操作
        if status_value == "waiting_user":
            # 🔴 强提醒：高亮闪烁警告
            st.error("🛑 **需要用户操作！**")

            # 使用 HTML 实现闪烁效果
            st.markdown("""
            <style>
            @keyframes blink {
                0% { opacity: 1; }
                50% { opacity: 0.3; }
                100% { opacity: 1; }
            }
            .blinking-warning {
                animation: blink 1.5s infinite;
                background-color: #ff4444;
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                font-size: 18px;
                font-weight: bold;
                margin: 10px 0;
            }
            </style>
            <div class="blinking-warning">
                ⚠️ 系统正在等待您的操作，请查看浏览器窗口 ⚠️
            </div>
            """, unsafe_allow_html=True)

            # 显示等待信息
            waiting_message = message or "系统正在等待您的操作"
            st.warning(f"📢 {waiting_message}")

            # 如果有当前职位信息，显示详情
            if current_job:
                with st.container():
                    st.markdown("---")
                    st.write("### 当前任务详情")
                    st.write(f"**职位**: {current_job.get('title', 'N/A')}")
                    st.write(f"**公司**: {current_job.get('company', 'N/A')}")
                    st.markdown("---")

            # 🔴 添加继续按钮
            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button("✅ 我已完成操作，继续", type="primary", use_container_width=True, key="continue_button"):
                    if HAS_INTERACTION_MANAGER:
                        interaction_mgr = get_interaction_manager(user_id=st.session_state.user_id)
                        interaction_mgr.set_signal("continue")
                        st.toast("✅ 已发送继续信号！", icon="✅")
                        st.success("✅ 已通知系统继续执行")
                        # 🔴 清理运行状态
                        reset_run_state()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 交互管理器未启用")

            with col_btn2:
                if st.button("❌ 取消任务", type="secondary", use_container_width=True, key="cancel_button"):
                    if HAS_INTERACTION_MANAGER:
                        interaction_mgr = get_interaction_manager(user_id=st.session_state.user_id)
                        interaction_mgr.set_signal("cancel")
                        st.toast("🛑 已发送取消信号", icon="🛑")
                        st.warning("🛑 已通知系统取消任务")
                        # 🔴 清理运行状态
                        reset_run_state()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 交互管理器未启用")

            # 添加提示信息
            st.info("""
            💡 **操作指南：**
            - 如果需要在浏览器中完成登录或投递操作，请先完成后再点击「继续」
            - 点击「继续」后，系统将自动恢复执行
            - 如果遇到问题，可以点击「取消任务」终止当前流程
            """)

        # 统计信息
        st.write("#### 📈 统计数据")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("总处理", stats.get("total_processed", 0))

        with col2:
            success_count = stats.get("success", 0)
            # 🔴 色彩语义：成功数量用绿色高亮
            st.metric("成功投递", success_count, delta_color="normal")

        with col3:
            st.metric("已跳过", stats.get("skipped", 0))

        with col4:
            st.metric("失败", stats.get("failed", 0), delta_color="inverse")

        # 🔴 仪式感：任务完成时触发庆祝动画
        if status_value == "completed" and success_count > 0:
            # 检查是否已经显示过庆祝动画（避免重复触发）
            if "celebration_shown" not in st.session_state:
                st.session_state.celebration_shown = True
                st.balloons()
                st.success(f"🎉 恭喜！成功投递 {success_count} 个职位！")

                # 显示汇总卡片
                with st.container():
                    st.markdown("---")
                    st.write("### 🎊 任务完成汇总")
                    summary_col1, summary_col2, summary_col3 = st.columns(3)
                    with summary_col1:
                        st.metric("✅ 成功", success_count)
                    with summary_col2:
                        st.metric("⏭️ 跳过", stats.get("skipped", 0))
                    with summary_col3:
                        st.metric("❌ 失败", stats.get("failed", 0))
                    st.markdown("---")
        elif status_value != "completed":
            # 重置庆祝标志（当任务重新开始时）
            if "celebration_shown" in st.session_state:
                del st.session_state.celebration_shown

    else:
        st.warning("⚠️ 状态管理器未启用，无法显示实时进度")
        st.info("💡 提示：请检查 core/status_manager.py 是否正确安装")

    # ===== 🔴 新增：远程物料中心 =====
    st.divider()
    st.write("### 📦 6. 远程物料中心")

    if HAS_REMOTE_ASSET_CENTER:
        # 使用 Fragment 实现自动刷新的物料中心
        remote_asset_center_fragment(user_id=st.session_state.user_id)
    else:
        st.warning("⚠️ 远程物料中心未启用")
        st.info("💡 提示：请检查 dashboard/remote_asset_center.py 是否正确安装")

    # ===== 🔴 隐藏：Profile 编辑器 =====
    # st.divider()
    # st.write("### 👤 7. 个人资料")
    #
    # if HAS_PROFILE_EDITOR:
    #     render_profile_editor(user_id=st.session_state.user_id)
    # else:
    #     st.warning("⚠️ Profile 编辑器未启用")
    #     st.info("💡 提示：请检查 dashboard/profile_editor.py 是否正确安装")

    # ===== 🔴 新增：投递历史 =====
    st.divider()
    st.write("### 📊 8. 投递历史")

    if HAS_JOB_HISTORY:
        # 使用 Fragment 实现自动刷新的投递历史
        job_history_fragment(user_id=st.session_state.user_id)
    else:
        st.warning("⚠️ 投递历史组件未启用")
        st.info("💡 提示：请检查 dashboard/job_history.py 是否正确安装")

    # 🔴 [关键修复] 自动刷新逻辑移到最后，确保所有内容都渲染完成
    # 这样用户能看到最新的状态，而不是旧的内容
    if HAS_STATUS_MANAGER:
        status_mgr = get_status_manager(user_id=st.session_state.user_id)
        current_status = status_mgr.read_status()
        status_value = current_status.get("status", "idle")

        # 检查自动刷新是否启用（初始化已在 init_session 中完成）
        auto_refresh_enabled = st.session_state.get("auto_refresh", True)

        # 🔴 [修复2] 清理已完成任务的状态
        # 如果任务已完成或出错，清除状态文件，避免下次打开还显示旧消息
        if status_value in ["completed", "error", "stopped"]:
            # 检查状态是否超过10秒未更新
            last_updated = current_status.get("last_updated", "")
            if last_updated:
                try:
                    from datetime import datetime
                    update_time = datetime.fromisoformat(last_updated)
                    time_diff = (datetime.now() - update_time).total_seconds()

                    # 如果状态超过10秒未更新，重置为 idle
                    if time_diff > 10:
                        status_mgr.reset()
                        st.caption(f"🧹 已清理旧状态 (上次更新: {int(time_diff)}秒前)")
                except:
                    pass

        # 只在活跃状态时触发自动刷新（包括 initializing）
        active_statuses = ["initializing", "scraping", "analyzing", "generating", "applying", "waiting_user", "manual_review"]

        # 🔴 自动刷新逻辑（移除调试信息显示）
        if auto_refresh_enabled and status_value in active_statuses:
            # 清空缓存确保下次刷新能显示新内容
            st.session_state.last_status_cache = {}

            # 🔴 [DEBUG] 在页面底部显示刷新倒计时
            st.write("---")
            st.write("### ⏱️ 刷新倒计时")
            placeholder = st.empty()
            for remaining in range(2, 0, -1):
                placeholder.caption(f"⏱️ {remaining} 秒后自动刷新... (状态: {status_value})")
                time.sleep(1)

            placeholder.caption("🔄 正在刷新...")
            time.sleep(0.2)
            st.rerun()

if __name__ == "__main__":
    main()
