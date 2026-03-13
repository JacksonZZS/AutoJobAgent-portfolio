"""
数据清理工具 - 自动清理过期临时文件
防止 data/ 目录下的临时文件无限增长

🔒 安全特性:
- 多租户数据隔离
- 基于user_id的权限控制
- 管理员专属全局清理
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Set, Optional

logger = logging.getLogger(__name__)

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data"

# 需要清理的文件扩展名
TEMP_FILE_EXTENSIONS = {".md", ".pdf", ".tmp"}

# 🔒 管理员账号列表
ADMIN_USERS = {"jackson", "admin", "root"}  # 小写用户名


def iter_temp_files(suffixes: Set[str] = None) -> List[Path]:
    """
    遍历 data/ 目录下的临时文件

    Args:
        suffixes: 文件扩展名集合,默认为 TEMP_FILE_EXTENSIONS

    Returns:
        临时文件路径列表
    """
    if suffixes is None:
        suffixes = TEMP_FILE_EXTENSIONS

    if not DATA_DIR.exists():
        logger.warning(f"数据目录不存在: {DATA_DIR}")
        return []

    temp_files = []
    for path in DATA_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            # 排除重要文件
            if should_exclude(path):
                continue
            temp_files.append(path)

    return temp_files


def should_exclude(path: Path) -> bool:
    """
    判断文件是否应该被排除(不清理)

    Args:
        path: 文件路径

    Returns:
        True 表示应该排除,False 表示可以清理
    """
    # 排除数据库文件
    if path.suffix in {".db", ".sqlite", ".sqlite3"}:
        return True

    # 排除配置文件
    if path.name in {"config.json", "settings.json"}:
        return True

    # 排除用户上传的简历(uploads目录)
    if "uploads" in path.parts:
        return True

    # 排除历史记录
    if "histories" in path.parts:
        return True

    # 排除浏览器配置
    if "browser_profiles" in path.parts:
        return True

    return False


def cleanup_data_dir(max_age_hours: int = 24, dry_run: bool = False) -> List[Path]:
    """
    清理 data/ 目录下超过指定时间的临时文件

    Args:
        max_age_hours: 最大文件年龄(小时),超过此时间的文件将被删除
        dry_run: 是否为演练模式(只列出文件,不实际删除)

    Returns:
        已删除(或将要删除)的文件路径列表
    """
    now = datetime.now()
    cutoff = now - timedelta(hours=max_age_hours)
    deleted = []

    logger.info(f"🧹 开始清理 data/ 目录 (最大年龄: {max_age_hours}小时)")

    for path in iter_temp_files():
        try:
            # 获取文件修改时间
            mtime = datetime.fromtimestamp(path.stat().st_mtime)

            if mtime < cutoff:
                if dry_run:
                    logger.info(f"[演练] 将删除: {path.relative_to(DATA_DIR)}")
                    deleted.append(path)
                else:
                    path.unlink()
                    logger.debug(f"✅ 已删除: {path.relative_to(DATA_DIR)}")
                    deleted.append(path)

        except Exception as e:
            logger.warning(f"⚠️ 删除文件失败: {path.relative_to(DATA_DIR)} - {e}")
            continue

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个文件")
    else:
        logger.info("ℹ️ 没有需要清理的文件")

    return deleted


def cleanup_all_temp_files(dry_run: bool = False) -> List[Path]:
    """
    清理 data/ 目录下所有临时文件(不考虑时间)

    警告: 此操作会删除所有临时文件,请谨慎使用

    Args:
        dry_run: 是否为演练模式(只列出文件,不实际删除)

    Returns:
        已删除(或将要删除)的文件路径列表
    """
    deleted = []

    logger.warning("⚠️ 开始清理所有临时文件 (不考虑时间)")

    for path in iter_temp_files():
        try:
            if dry_run:
                logger.info(f"[演练] 将删除: {path.relative_to(DATA_DIR)}")
                deleted.append(path)
            else:
                path.unlink()
                logger.debug(f"✅ 已删除: {path.relative_to(DATA_DIR)}")
                deleted.append(path)

        except Exception as e:
            logger.warning(f"⚠️ 删除文件失败: {path.relative_to(DATA_DIR)} - {e}")
            continue

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个文件")
    else:
        logger.info("ℹ️ 没有需要清理的文件")

    return deleted


def cleanup_outputs_for_user(user_id: str, max_age_hours: int = 24, dry_run: bool = False) -> List[Path]:
    """
    清理指定用户的输出文件

    Args:
        user_id: 用户ID
        max_age_hours: 最大文件年龄(小时)
        dry_run: 是否为演练模式

    Returns:
        已删除(或将要删除)的文件路径列表
    """
    user_output_dir = DATA_DIR / "outputs" / str(user_id)

    if not user_output_dir.exists():
        logger.info(f"ℹ️ 用户输出目录不存在: {user_output_dir}")
        return []

    now = datetime.now()
    cutoff = now - timedelta(hours=max_age_hours)
    deleted = []

    logger.info(f"🧹 开始清理用户 {user_id} 的输出文件 (最大年龄: {max_age_hours}小时)")

    for path in user_output_dir.rglob("*"):
        if not path.is_file():
            continue

        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)

            if mtime < cutoff:
                if dry_run:
                    logger.info(f"[演练] 将删除: {path.relative_to(DATA_DIR)}")
                    deleted.append(path)
                else:
                    path.unlink()
                    logger.debug(f"✅ 已删除: {path.relative_to(DATA_DIR)}")
                    deleted.append(path)

        except Exception as e:
            logger.warning(f"⚠️ 删除文件失败: {path.relative_to(DATA_DIR)} - {e}")
            continue

    # 清理空目录
    if not dry_run:
        try:
            for dir_path in sorted(user_output_dir.rglob("*"), reverse=True):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    logger.debug(f"✅ 已删除空目录: {dir_path.relative_to(DATA_DIR)}")
        except Exception as e:
            logger.warning(f"⚠️ 清理空目录失败: {e}")

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个文件")
    else:
        logger.info("ℹ️ 没有需要清理的文件")

    return deleted


def get_data_dir_size() -> dict:
    """
    获取 data/ 目录的大小统计

    Returns:
        包含总大小和文件数量的字典
    """
    total_size = 0
    file_count = 0
    temp_file_count = 0
    temp_file_size = 0

    if not DATA_DIR.exists():
        return {
            "total_size_mb": 0,
            "file_count": 0,
            "temp_file_count": 0,
            "temp_file_size_mb": 0
        }

    for path in DATA_DIR.rglob("*"):
        if path.is_file():
            size = path.stat().st_size
            total_size += size
            file_count += 1

            if path.suffix.lower() in TEMP_FILE_EXTENSIONS and not should_exclude(path):
                temp_file_count += 1
                temp_file_size += size

    return {
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "file_count": file_count,
        "temp_file_count": temp_file_count,
        "temp_file_size_mb": round(temp_file_size / (1024 * 1024), 2)
    }


# 🔒 ==================== 多租户安全清理函数 ====================

def is_admin(user_id: str) -> bool:
    """
    检查用户是否为管理员

    Args:
        user_id: 用户ID

    Returns:
        True 表示是管理员,False 表示不是
    """
    if not user_id:
        return False

    # 转换为小写进行比较
    username = user_id.lower().strip()

    return username in ADMIN_USERS


def cleanup_user_history(user_id: str, dry_run: bool = False) -> List[Path]:
    """
    🔒 清理指定用户的历史记录(多租户安全)

    Args:
        user_id: 用户ID
        dry_run: 是否为演练模式

    Returns:
        已删除(或将要删除)的文件路径列表
    """
    if not user_id:
        logger.error("❌ user_id 不能为空")
        return []

    deleted = []

    logger.info(f"🧹 开始清理用户 {user_id} 的历史记录")

    # 用户专属历史文件
    user_history_file = DATA_DIR / "histories" / f"history_{user_id}.json"

    if user_history_file.exists():
        if dry_run:
            logger.info(f"[演练] 将删除: {user_history_file.relative_to(DATA_DIR)}")
            deleted.append(user_history_file)
        else:
            user_history_file.unlink()
            logger.info(f"✅ 已删除: {user_history_file.relative_to(DATA_DIR)}")
            deleted.append(user_history_file)

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个文件")
    else:
        logger.info("ℹ️ 没有历史记录需要清理")

    return deleted


def cleanup_user_browser_profile(user_id: str, dry_run: bool = False) -> List[Path]:
    """
    🔒 清理指定用户的浏览器配置(多租户安全)

    Args:
        user_id: 用户ID
        dry_run: 是否为演练模式

    Returns:
        已删除(或将要删除)的目录路径列表
    """
    if not user_id:
        logger.error("❌ user_id 不能为空")
        return []

    deleted = []

    logger.info(f"🗑️ 开始清理用户 {user_id} 的浏览器配置")

    # 用户专属浏览器配置目录
    user_profile_dir = DATA_DIR / "browser_profiles" / user_id

    if user_profile_dir.exists():
        if dry_run:
            logger.info(f"[演练] 将删除: {user_profile_dir.relative_to(DATA_DIR)}")
            deleted.append(user_profile_dir)
        else:
            shutil.rmtree(user_profile_dir)
            logger.info(f"✅ 已删除: {user_profile_dir.relative_to(DATA_DIR)}")
            deleted.append(user_profile_dir)

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个目录")
    else:
        logger.info("ℹ️ 没有浏览器配置需要清理")

    return deleted


def cleanup_user_temp_files(user_id: str, max_age_hours: int = 24, dry_run: bool = False) -> List[Path]:
    """
    🔒 清理指定用户的临时文件(多租户安全)

    Args:
        user_id: 用户ID
        max_age_hours: 最大文件年龄(小时)
        dry_run: 是否为演练模式

    Returns:
        已删除(或将要删除)的文件路径列表
    """
    if not user_id:
        logger.error("❌ user_id 不能为空")
        return []

    deleted = []
    now = datetime.now()
    cutoff = now - timedelta(hours=max_age_hours)

    logger.info(f"✨ 开始清理用户 {user_id} 的临时文件 (最大年龄: {max_age_hours}小时)")

    # 用户专属输出目录
    user_output_dir = DATA_DIR / "outputs" / user_id

    if not user_output_dir.exists():
        logger.info(f"ℹ️ 用户输出目录不存在: {user_output_dir}")
        return []

    for path in user_output_dir.rglob("*"):
        if not path.is_file():
            continue

        # 只清理临时文件
        if path.suffix.lower() not in TEMP_FILE_EXTENSIONS:
            continue

        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)

            if mtime < cutoff:
                if dry_run:
                    logger.info(f"[演练] 将删除: {path.relative_to(DATA_DIR)}")
                    deleted.append(path)
                else:
                    path.unlink()
                    logger.debug(f"✅ 已删除: {path.relative_to(DATA_DIR)}")
                    deleted.append(path)

        except Exception as e:
            logger.warning(f"⚠️ 删除文件失败: {path.relative_to(DATA_DIR)} - {e}")
            continue

    # 清理空目录
    if not dry_run:
        try:
            for dir_path in sorted(user_output_dir.rglob("*"), reverse=True):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    logger.debug(f"✅ 已删除空目录: {dir_path.relative_to(DATA_DIR)}")
        except Exception as e:
            logger.warning(f"⚠️ 清理空目录失败: {e}")

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个文件")
    else:
        logger.info("ℹ️ 没有临时文件需要清理")

    return deleted


def cleanup_user_all_data(user_id: str, dry_run: bool = False) -> dict:
    """
    🔒 清理指定用户的所有数据(多租户安全)

    Args:
        user_id: 用户ID
        dry_run: 是否为演练模式

    Returns:
        包含各类清理结果的字典
    """
    if not user_id:
        logger.error("❌ user_id 不能为空")
        return {}

    logger.warning(f"⚠️ 开始清理用户 {user_id} 的所有数据")

    results = {
        "history": cleanup_user_history(user_id, dry_run),
        "browser_profile": cleanup_user_browser_profile(user_id, dry_run),
        "temp_files": cleanup_user_temp_files(user_id, max_age_hours=0, dry_run=dry_run)  # 清理所有临时文件
    }

    total_deleted = sum(len(v) for v in results.values())
    logger.info(f"✅ 用户数据清理完成,共删除 {total_deleted} 项")

    return results


# 🔥 ==================== 管理员专属全局清理函数 ====================

def admin_cleanup_all_histories(admin_user_id: str, dry_run: bool = False) -> List[Path]:
    """
    🔥 管理员专属:清理所有用户的历史记录

    Args:
        admin_user_id: 管理员用户ID
        dry_run: 是否为演练模式

    Returns:
        已删除(或将要删除)的文件路径列表
    """
    if not is_admin(admin_user_id):
        logger.error(f"❌ 权限拒绝: {admin_user_id} 不是管理员")
        raise PermissionError(f"User {admin_user_id} is not an admin")

    deleted = []

    logger.warning("🔥 管理员操作:开始清理所有历史记录")

    # 清理所有用户的历史文件
    histories_dir = DATA_DIR / "histories"
    if histories_dir.exists():
        for history_file in histories_dir.glob("history_*.json"):
            if dry_run:
                logger.info(f"[演练] 将删除: {history_file.relative_to(DATA_DIR)}")
                deleted.append(history_file)
            else:
                history_file.unlink()
                logger.info(f"✅ 已删除: {history_file.relative_to(DATA_DIR)}")
                deleted.append(history_file)

    # 清理旧的全局历史文件
    old_history_file = DATA_DIR / "job_history.json"
    if old_history_file.exists():
        if dry_run:
            logger.info(f"[演练] 将删除: {old_history_file.relative_to(DATA_DIR)}")
            deleted.append(old_history_file)
        else:
            old_history_file.unlink()
            logger.info(f"✅ 已删除: {old_history_file.relative_to(DATA_DIR)}")
            deleted.append(old_history_file)

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个文件")
    else:
        logger.info("ℹ️ 没有历史记录需要清理")

    return deleted


def admin_cleanup_all_browser_profiles(admin_user_id: str, dry_run: bool = False) -> List[Path]:
    """
    🔥 管理员专属:清理所有浏览器配置

    Args:
        admin_user_id: 管理员用户ID
        dry_run: 是否为演练模式

    Returns:
        已删除(或将要删除)的目录路径列表
    """
    if not is_admin(admin_user_id):
        logger.error(f"❌ 权限拒绝: {admin_user_id} 不是管理员")
        raise PermissionError(f"User {admin_user_id} is not an admin")

    deleted = []

    logger.warning("🔥 管理员操作:开始清理所有浏览器配置")

    browser_profiles_dir = DATA_DIR / "browser_profiles"
    if browser_profiles_dir.exists():
        if dry_run:
            logger.info(f"[演练] 将删除: {browser_profiles_dir.relative_to(DATA_DIR)}")
            deleted.append(browser_profiles_dir)
        else:
            shutil.rmtree(browser_profiles_dir)
            logger.info(f"✅ 已删除: {browser_profiles_dir.relative_to(DATA_DIR)}")
            deleted.append(browser_profiles_dir)

            # 重新创建目录
            browser_profiles_dir.mkdir(parents=True, exist_ok=True)

    if deleted:
        logger.info(f"✅ 清理完成,共删除 {len(deleted)} 个目录")
    else:
        logger.info("ℹ️ 没有浏览器配置需要清理")

    return deleted


def admin_cleanup_all_temp_files(admin_user_id: str, dry_run: bool = False) -> List[Path]:
    """
    🔥 管理员专属:清理所有临时文件

    Args:
        admin_user_id: 管理员用户ID
        dry_run: 是否为演练模式

    Returns:
        已删除(或将要删除)的文件路径列表
    """
    if not is_admin(admin_user_id):
        logger.error(f"❌ 权限拒绝: {admin_user_id} 不是管理员")
        raise PermissionError(f"User {admin_user_id} is not an admin")

    logger.warning("🔥 管理员操作:开始清理所有临时文件")

    # 使用现有的全局清理函数
    return cleanup_all_temp_files(dry_run=dry_run)


def admin_full_system_cleanup(admin_user_id: str, dry_run: bool = False) -> dict:
    """
    🔥 管理员专属:全系统大扫除

    Args:
        admin_user_id: 管理员用户ID
        dry_run: 是否为演练模式

    Returns:
        包含各类清理结果的字典
    """
    if not is_admin(admin_user_id):
        logger.error(f"❌ 权限拒绝: {admin_user_id} 不是管理员")
        raise PermissionError(f"User {admin_user_id} is not an admin")

    logger.warning("🔥🔥🔥 管理员操作:全系统大扫除 🔥🔥🔥")

    results = {
        "histories": admin_cleanup_all_histories(admin_user_id, dry_run),
        "browser_profiles": admin_cleanup_all_browser_profiles(admin_user_id, dry_run),
        "temp_files": admin_cleanup_all_temp_files(admin_user_id, dry_run)
    }

    total_deleted = sum(len(v) for v in results.values())
    logger.warning(f"🔥 全系统清理完成,共删除 {total_deleted} 项")

    return results


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 演练模式:查看将要删除的文件
    print("\n=== 演练模式:查看将要删除的文件 ===")
    cleanup_data_dir(max_age_hours=24, dry_run=True)

    # 获取目录大小统计
    print("\n=== data/ 目录统计 ===")
    stats = get_data_dir_size()
    print(f"总大小: {stats['total_size_mb']} MB")
    print(f"文件数量: {stats['file_count']}")
    print(f"临时文件数量: {stats['temp_file_count']}")
    print(f"临时文件大小: {stats['temp_file_size_mb']} MB")
