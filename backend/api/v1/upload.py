"""
文件上传 API 路由
处理简历和成绩单的上传，集成缓存检查
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pathlib import Path
import hashlib
import json
from typing import Optional
from datetime import datetime

# 导入核心业务模块
from core.llm_engine import LLMEngine

# 导入认证依赖
from backend.api.v1.auth import get_current_user
from backend.models.schemas import (
    UserInfo,
    UploadResumeResponse,
    UploadTranscriptResponse,
    ResumeInfo,
    ResumeListResponse,
    MessageResponse
)

router = APIRouter(prefix="/upload", tags=["File Upload"])

# 配置
UPLOAD_DIR = Path("data/uploads")
ANALYSIS_CACHE_FILE = Path("data/analysis_cache.json")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ============================================================
# 工具函数
# ============================================================

def calculate_file_hash(file_bytes: bytes, user_id: int) -> str:
    """
    计算文件哈希值（用于缓存）

    Args:
        file_bytes: 文件二进制内容
        user_id: 用户 ID（用于多用户隔离）

    Returns:
        SHA256 哈希值
    """
    hasher = hashlib.sha256()  # 🔴 修复: MD5 -> SHA256
    hasher.update(file_bytes)
    hasher.update(str(user_id).encode())  # 加入 user_id 确保隔离
    return hasher.hexdigest()


def get_cached_analysis(file_hash: str) -> Optional[dict]:
    """
    从缓存中获取分析结果

    Args:
        file_hash: 文件哈希值

    Returns:
        缓存的分析结果，如果不存在返回 None
    """
    if not ANALYSIS_CACHE_FILE.exists():
        return None

    try:
        with open(ANALYSIS_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        if file_hash in cache:
            cached_data = cache[file_hash]
            # 返回缓存的搜索策略
            return {
                "keywords": cached_data.get("keywords", ""),
                "blocked_companies": cached_data.get("blocked_companies", ""),
                "title_exclusions": cached_data.get("title_exclusions", ""),
                "cached": True
            }
    except Exception as e:
        print(f"Failed to read cache: {e}")

    return None


def save_to_cache(file_hash: str, analysis_result: dict):
    """
    保存分析结果到缓存

    Args:
        file_hash: 文件哈希值
        analysis_result: 分析结果
    """
    try:
        # 读取现有缓存
        if ANALYSIS_CACHE_FILE.exists():
            with open(ANALYSIS_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        else:
            cache = {}

        # 更新缓存
        cache[file_hash] = {
            **analysis_result,
            "timestamp": datetime.now().timestamp()
        }

        # 写回缓存文件
        ANALYSIS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ANALYSIS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"Failed to save cache: {e}")


# ============================================================
# API 端点
# ============================================================

@router.get("/last-upload")
async def get_last_upload(current_user: UserInfo = Depends(get_current_user)):
    """
    获取用户上次上传的文档信息

    **功能**：
    - 检查用户是否有已上传的简历和成绩单
    - 返回文件路径和缓存的分析结果
    - 前端可用于"继续上次任务"功能
    """
    user_upload_dir = UPLOAD_DIR / f"user_{current_user.id}"

    result = {
        "has_resume": False,
        "resume_path": None,
        "resume_filename": None,
        "has_transcript": False,
        "transcript_path": None,
        "transcript_filename": None,
        "cached_analysis": None,
        "last_platform": None  # 🔴 记住上次使用的平台
    }

    # 🔴 从 last_resume.json 读取上次上传的简历信息
    meta_path = user_upload_dir / "last_resume.json"
    if meta_path.exists():
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                last_meta = json.load(f)
            resume_path = Path(last_meta.get("file_path", ""))
            if resume_path.exists():
                result["has_resume"] = True
                result["resume_path"] = str(resume_path.absolute())
                result["resume_filename"] = last_meta.get("original_filename") or last_meta.get("filename")

                # 读取文件哈希并检查缓存
                file_hash = last_meta.get("file_hash")
                if file_hash:
                    cached = get_cached_analysis(file_hash)
                    if cached:
                        result["cached_analysis"] = cached
                        # 🔴 从缓存中读取上次使用的平台
                        result["last_platform"] = cached.get("last_platform", "jobsdb")
        except Exception as e:
            print(f"[last-upload] 读取 last_resume.json 失败: {e}")

    # 检查成绩单
    transcript_path = user_upload_dir / f"{current_user.username}_transcript.pdf"
    if transcript_path.exists():
        result["has_transcript"] = True
        result["transcript_path"] = str(transcript_path.absolute())
        result["transcript_filename"] = f"{current_user.username}_transcript.pdf"

    return result


@router.post("/resume", response_model=UploadResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    上传简历文件

    - 支持 PDF 格式
    - 自动计算文件哈希并检查缓存
    - 文件保存到 data/uploads/user_{user_id}/ 目录
    - 如果缓存命中，自动返回历史分析结果
    """

    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )

    # 读取文件内容
    file_bytes = await file.read()

    # 检查文件大小
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE / 1024 / 1024} MB"
        )

    # 计算文件哈希
    file_hash = calculate_file_hash(file_bytes, current_user.id)

    # 检查缓存
    cached_analysis = get_cached_analysis(file_hash)

    # 保存文件
    user_upload_dir = UPLOAD_DIR / f"user_{current_user.id}"
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    # 🔴 保留原始文件名（去掉路径，只保留文件名）
    original_filename = Path(file.filename).name
    # 安全处理文件名（移除特殊字符）
    safe_filename = "".join(c for c in original_filename if c.isalnum() or c in ('_', '-', '.', ' ')).strip()
    if not safe_filename.endswith('.pdf'):
        safe_filename += '.pdf'

    save_path = user_upload_dir / safe_filename

    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    # 🔴 记录最后上传的简历信息（用于 check-status）
    last_upload_meta = {
        "filename": safe_filename,
        "original_filename": original_filename,
        "file_path": str(save_path.absolute()),
        "file_hash": file_hash,
        "uploaded_at": datetime.now().isoformat()
    }
    meta_path = user_upload_dir / "last_resume.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(last_upload_meta, f, ensure_ascii=False, indent=2)

    # 构造响应
    if cached_analysis:
        return UploadResumeResponse(
            file_path=str(save_path.absolute()),
            file_hash=file_hash,
            cached_analysis=cached_analysis,
            message="⚡️ 检测到已有记录，已秒速加载历史分析结果"
        )
    else:
        return UploadResumeResponse(
            file_path=str(save_path.absolute()),
            file_hash=file_hash,
            cached_analysis=None,
            message="💡 这是新简历，请调用 /analysis/analyze-resume 进行分析"
        )


@router.post("/transcript", response_model=UploadTranscriptResponse)
async def upload_transcript(
    file: UploadFile = File(...),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    上传成绩单文件

    - 支持 PDF 格式
    - 文件保存到 data/uploads/user_{user_id}/ 目录
    - 可选文件，用于辅助简历分析
    - 🔴 如果和简历相同，自动跳过（避免重复分析）
    """
    print(f"=" * 80)
    print(f"[成绩单上传] 开始处理")
    print(f"[成绩单上传] 用户: {current_user.username} (ID: {current_user.id})")
    print(f"[成绩单上传] 文件名: {file.filename}")
    print(f"=" * 80)

    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        print(f"[成绩单上传] ❌ 文件格式错误: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )

    # 读取文件内容
    try:
        file_bytes = await file.read()
        print(f"[成绩单上传] ✅ 文件读取成功，大小: {len(file_bytes)} bytes")
    except Exception as e:
        print(f"[成绩单上传] ❌ 文件读取失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )

    # 检查文件大小
    if len(file_bytes) > MAX_FILE_SIZE:
        print(f"[成绩单上传] ❌ 文件过大: {len(file_bytes)} bytes")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE / 1024 / 1024} MB"
        )

    # 🔴 检查是否和简历相同
    user_upload_dir = UPLOAD_DIR / f"user_{current_user.id}"
    resume_path = user_upload_dir / f"{current_user.username}_resume.pdf"

    if resume_path.exists():
        try:
            with open(resume_path, 'rb') as f:
                resume_bytes = f.read()

            # 比较文件哈希
            transcript_hash = hashlib.md5(file_bytes).hexdigest()
            resume_hash = hashlib.md5(resume_bytes).hexdigest()

            if transcript_hash == resume_hash:
                print(f"[成绩单上传] ⚡️ 检测到成绩单与简历相同，跳过保存")
                return UploadTranscriptResponse(
                    file_path="",  # 空路径表示跳过
                    message="⚡️ 成绩单与简历相同，已自动跳过（无需重复分析）"
                )
        except Exception as e:
            print(f"[成绩单上传] ⚠️ 比较文件时出错: {e}")

    # 保存文件
    try:
        user_upload_dir.mkdir(parents=True, exist_ok=True)
        print(f"[成绩单上传] 保存目录: {user_upload_dir}")

        save_path = user_upload_dir / f"{current_user.username}_transcript.pdf"

        with open(save_path, 'wb') as f:
            f.write(file_bytes)

        print(f"[成绩单上传] ✅ 文件保存成功: {save_path}")
    except Exception as e:
        print(f"[成绩单上传] ❌ 文件保存失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    print(f"[成绩单上传] ✅ 上传完成")
    print(f"=" * 80)

    return UploadTranscriptResponse(
        file_path=str(save_path.absolute()),
        message="成绩单上传成功"
    )


@router.get("/cache-status/{file_hash}")
async def check_cache_status(
    file_hash: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    检查文件缓存状态

    - 前端可用此端点检查是否有历史分析结果
    - 如果有缓存，返回缓存的分析结果
    """
    cached_analysis = get_cached_analysis(file_hash)

    if cached_analysis:
        return {
            "cached": True,
            "analysis": cached_analysis,
            "message": "找到缓存的分析结果"
        }
    else:
        return {
            "cached": False,
            "analysis": None,
            "message": "未找到缓存"
        }


# ============================================================
# 多简历管理 API
# ============================================================

RESUME_MANIFEST_FILE = "resume_manifest.json"


def get_resume_manifest_path(user_id: str) -> Path:
    """获取用户简历清单文件路径"""
    return UPLOAD_DIR / f"user_{user_id}" / RESUME_MANIFEST_FILE


def load_resume_manifest(user_id: str) -> dict:
    """加载用户简历清单"""
    path = get_resume_manifest_path(user_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"resumes": [], "default_resume_id": None}


def save_resume_manifest(user_id: str, data: dict):
    """保存用户简历清单"""
    path = get_resume_manifest_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


@router.get("/resumes", response_model=ResumeListResponse)
async def list_resumes(current_user: UserInfo = Depends(get_current_user)):
    """
    列出用户所有简历

    **功能**：
    - 返回用户上传的所有简历列表
    - 包含标签、是否默认等信息
    """
    manifest = load_resume_manifest(str(current_user.id))

    resumes = []
    for r in manifest.get("resumes", []):
        try:
            uploaded_at = datetime.fromisoformat(r.get("uploaded_at", ""))
        except:
            uploaded_at = datetime.now()

        resumes.append(ResumeInfo(
            resume_id=r.get("resume_id", ""),
            filename=r.get("filename", ""),
            label=r.get("label"),
            file_path=r.get("file_path", ""),
            file_hash=r.get("file_hash", ""),
            is_default=r.get("is_default", False),
            uploaded_at=uploaded_at
        ))

    return ResumeListResponse(
        resumes=resumes,
        default_resume_id=manifest.get("default_resume_id")
    )


@router.post("/resume-with-label", response_model=MessageResponse)
async def upload_resume_with_label(
    file: UploadFile = File(...),
    label: Optional[str] = None,
    is_default: bool = False,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    上传简历（带标签）

    **功能**：
    - 上传简历并设置标签（如 DS/BA/PM）
    - 可设置为默认简历
    - 支持多简历管理
    """
    import uuid

    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )

    # 读取文件
    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large"
        )

    # 生成唯一 ID 和哈希
    resume_id = str(uuid.uuid4())[:8]
    file_hash = calculate_file_hash(file_bytes, current_user.id)

    # 保存文件
    user_upload_dir = UPLOAD_DIR / f"user_{current_user.id}"
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    # 🔴 安全修复: 清洗 label 防止路径遍历
    import re
    def sanitize_label(lbl: str) -> str:
        if not lbl:
            return "default"
        safe = re.sub(r'[^a-zA-Z0-9_\-]', '', lbl.replace(" ", "_"))
        safe = safe.replace('..', '').strip()
        return safe[:30] if safe else "default"

    safe_label = sanitize_label(label)
    save_filename = f"resume_{safe_label}_{resume_id}.pdf"
    save_path = user_upload_dir / save_filename

    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    # 更新清单
    manifest = load_resume_manifest(str(current_user.id))

    # 检查简历数量限制
    if len(manifest.get("resumes", [])) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最多只能上传 5 份简历，请删除旧简历后再上传"
        )

    # 添加新简历
    new_resume = {
        "resume_id": resume_id,
        "filename": save_filename,
        "label": label,
        "file_path": str(save_path.absolute()),
        "file_hash": file_hash,
        "is_default": is_default,
        "uploaded_at": datetime.now().isoformat()
    }

    if "resumes" not in manifest:
        manifest["resumes"] = []

    # 如果设为默认，取消其他简历的默认状态
    if is_default:
        for r in manifest["resumes"]:
            r["is_default"] = False
        manifest["default_resume_id"] = resume_id

    manifest["resumes"].append(new_resume)

    # 如果是第一份简历，自动设为默认
    if len(manifest["resumes"]) == 1:
        manifest["resumes"][0]["is_default"] = True
        manifest["default_resume_id"] = resume_id

    save_resume_manifest(str(current_user.id), manifest)

    return MessageResponse(
        message=f"简历上传成功: {label or '默认'}",
        status="success",
        data={"resume_id": resume_id, "filename": save_filename}
    )


@router.put("/resume/{resume_id}/default", response_model=MessageResponse)
async def set_default_resume(
    resume_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    设置默认简历

    **功能**：
    - 将指定简历设为默认
    - 任务启动时默认使用此简历
    """
    manifest = load_resume_manifest(str(current_user.id))

    found = False
    for r in manifest.get("resumes", []):
        if r["resume_id"] == resume_id:
            r["is_default"] = True
            manifest["default_resume_id"] = resume_id
            found = True
        else:
            r["is_default"] = False

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    save_resume_manifest(str(current_user.id), manifest)

    return MessageResponse(
        message="已设为默认简历",
        status="success",
        data={"resume_id": resume_id}
    )


@router.delete("/resume/{resume_id}", response_model=MessageResponse)
async def delete_resume(
    resume_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    删除简历

    **功能**：
    - 从清单中移除简历
    - 删除对应的文件
    """
    manifest = load_resume_manifest(str(current_user.id))

    resume_to_delete = None
    for r in manifest.get("resumes", []):
        if r["resume_id"] == resume_id:
            resume_to_delete = r
            break

    if not resume_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )

    # 删除文件
    # 🔴 安全修复: 验证文件路径在用户目录内
    file_path = Path(resume_to_delete["file_path"]).resolve()
    user_upload_dir = (UPLOAD_DIR / f"user_{current_user.id}").resolve()

    if not str(file_path).startswith(str(user_upload_dir)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Invalid file path"
        )

    if file_path.exists():
        file_path.unlink()

    # 从清单中移除
    manifest["resumes"] = [r for r in manifest["resumes"] if r["resume_id"] != resume_id]

    # 如果删除的是默认简历，重新设置默认
    if manifest.get("default_resume_id") == resume_id:
        if manifest["resumes"]:
            manifest["resumes"][0]["is_default"] = True
            manifest["default_resume_id"] = manifest["resumes"][0]["resume_id"]
        else:
            manifest["default_resume_id"] = None

    save_resume_manifest(str(current_user.id), manifest)

    return MessageResponse(
        message=f"已删除简历: {resume_to_delete.get('label', '默认')}",
        status="success",
        data={"resume_id": resume_id}
    )
