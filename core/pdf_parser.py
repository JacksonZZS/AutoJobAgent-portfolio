import pdfplumber
import hashlib
import json
import os
from pathlib import Path

# 缓存文件路径
CACHE_DIR = Path(__file__).parent.parent / "data"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_CACHE_FILE = CACHE_DIR / "transcript_cache.json"

def calculate_file_hash(file_path):
    """计算文件的 MD5 哈希值"""
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            return hashlib.md5(file_bytes).hexdigest()
    except Exception as e:
        print(f"⚠️ 计算文件哈希失败: {e}")
        return None

def load_transcript_cache():
    """加载成绩单缓存"""
    if TRANSCRIPT_CACHE_FILE.exists():
        try:
            with open(TRANSCRIPT_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载成绩单缓存失败: {e}")
            return {}
    return {}

def save_transcript_cache(cache_data):
    """保存成绩单缓存"""
    try:
        with open(TRANSCRIPT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存成绩单缓存失败: {e}")

def extract_text_from_pdf(pdf_path, use_cache=True):
    """
    把成绩单 PDF 转换成纯文本，给 Claude 看

    Args:
        pdf_path: PDF 文件路径
        use_cache: 是否使用缓存（默认 True）

    Returns:
        提取的文本内容
    """
    # ✅ Cache-First Strategy
    if use_cache:
        # 1. 计算文件哈希
        file_hash = calculate_file_hash(pdf_path)

        if file_hash:
            # 2. 检查缓存
            cache = load_transcript_cache()

            if file_hash in cache:
                # 命中缓存
                print(f"DEBUG: ⚡️ 命中成绩单缓存，加载速度 < 0.1s (Hash: {file_hash[:16]}...)")
                return cache[file_hash]["text"]
            else:
                print(f"DEBUG: 📄 未命中缓存，开始解析 PDF... (Hash: {file_hash[:16]}...)")

    # 3. 未命中或禁用缓存 - 执行原有解析逻辑
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # 提取每一页的文字
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        # 4. 保存到缓存
        if use_cache and file_hash:
            cache = load_transcript_cache()
            cache[file_hash] = {
                "text": full_text,
                "file_path": str(pdf_path),
                "timestamp": os.path.getmtime(pdf_path)
            }
            save_transcript_cache(cache)
            print(f"DEBUG: 💾 已保存到缓存 (Hash: {file_hash[:16]}...)")

        return full_text
    except Exception as e:
        return f"Error reading PDF: {e}"

# 测试用的
if __name__ == "__main__":
    text = extract_text_from_pdf("../data/inputs/transcript.pdf")
    print(text[:500]) # 打印前500个字看看对不对