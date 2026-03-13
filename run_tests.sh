#!/bin/bash

# 快速测试脚本
# 按顺序运行所有测试

echo "🧪 AutoJobAgent 自动投递功能测试套件"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python 3"
    exit 1
fi

echo "✅ Python 已安装: $(python3 --version)"
echo ""

# 检查依赖
echo "📦 检查依赖..."
if ! python3 -c "import playwright" 2>/dev/null; then
    echo "⚠️ Playwright 未安装"
    echo "正在安装依赖..."
    pip install -r requirements.txt
    playwright install chromium
fi

echo "✅ 依赖已安装"
echo ""

# 检查环境变量
echo "🔍 检查环境变量..."
if [ ! -f .env ]; then
    echo "⚠️ 未找到 .env 文件"
    echo "请创建 .env 文件并配置以下变量:"
    echo "  ANTHROPIC_API_KEY=your_key"
    echo "  JOBSDB_USERNAME=your_email"
    echo "  JOBSDB_PASSWORD=your_password"
    exit 1
fi

echo "✅ .env 文件存在"
echo ""

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p data/sessions
mkdir -p data/logs
mkdir -p tests
echo "✅ 目录已创建"
echo ""

# 测试 1: Cover Letter 生成
echo "========================================"
echo "测试 1/4: Cover Letter 生成"
echo "========================================"
echo ""
python3 tests/test_01_cover_letter.py
TEST1_RESULT=$?
echo ""

if [ $TEST1_RESULT -ne 0 ]; then
    echo "❌ 测试 1 失败，停止后续测试"
    exit 1
fi

# 测试 2: 浏览器启动
echo "========================================"
echo "测试 2/4: 浏览器启动"
echo "========================================"
echo ""
python3 tests/test_02_browser.py
TEST2_RESULT=$?
echo ""

if [ $TEST2_RESULT -ne 0 ]; then
    echo "❌ 测试 2 失败，停止后续测试"
    exit 1
fi

# 测试 3: 登录功能
echo "========================================"
echo "测试 3/4: 登录功能"
echo "========================================"
echo ""
echo "⚠️ 这个测试需要真实的 JobsDB 账号"
echo "⚠️ 如果出现验证码，请在浏览器中手动完成"
echo ""
read -p "按 Enter 键继续，或 Ctrl+C 取消..."
echo ""

python3 tests/test_03_login.py
TEST3_RESULT=$?
echo ""

if [ $TEST3_RESULT -ne 0 ]; then
    echo "❌ 测试 3 失败"
    echo "您可以继续测试其他功能，但投递功能可能无法使用"
    read -p "按 Enter 键继续，或 Ctrl+C 退出..."
fi

# 测试 4: 单个职位投递
echo "========================================"
echo "测试 4/4: 单个职位投递"
echo "========================================"
echo ""
echo "⚠️ 这个测试会真实投递简历！"
echo "⚠️ 建议使用已投递过的职位进行测试"
echo ""
read -p "是否继续? (yes/no): " CONTINUE

if [ "$CONTINUE" != "yes" ]; then
    echo "跳过测试 4"
    TEST4_RESULT=0
else
    python3 tests/test_04_single_apply.py
    TEST4_RESULT=$?
fi

echo ""

# 总结
echo "========================================"
echo "测试总结"
echo "========================================"
echo ""
echo "测试 1 (Cover Letter): $([ $TEST1_RESULT -eq 0 ] && echo '✅ 通过' || echo '❌ 失败')"
echo "测试 2 (浏览器):       $([ $TEST2_RESULT -eq 0 ] && echo '✅ 通过' || echo '❌ 失败')"
echo "测试 3 (登录):         $([ $TEST3_RESULT -eq 0 ] && echo '✅ 通过' || echo '❌ 失败')"
echo "测试 4 (投递):         $([ $TEST4_RESULT -eq 0 ] && echo '✅ 通过' || echo '⏭️ 跳过')"
echo ""

if [ $TEST1_RESULT -eq 0 ] && [ $TEST2_RESULT -eq 0 ] && [ $TEST3_RESULT -eq 0 ]; then
    echo "🎉 核心功能测试通过！"
    echo ""
    echo "下一步:"
    echo "1. 查看 TESTING_GUIDE.md 了解详细测试说明"
    echo "2. 查看 example_auto_apply.py 了解如何集成"
    echo "3. 根据需要调整配置和参数"
    echo ""
else
    echo "⚠️ 部分测试失败，请查看上面的错误信息"
    echo ""
    echo "常见问题:"
    echo "1. API Key 错误 -> 检查 .env 文件"
    echo "2. 浏览器启动失败 -> 运行 'playwright install chromium'"
    echo "3. 登录失败 -> 检查账号密码，处理验证码"
    echo ""
    echo "详细排查指南请查看 TESTING_GUIDE.md"
    echo ""
fi
