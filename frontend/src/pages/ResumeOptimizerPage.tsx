import React, { useState } from 'react';
import { Upload, FileText, Sparkles, Download, Check, ChevronRight, ChevronLeft } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { resumeOptimizerAPI } from '@/api/resumeOptimizer';

/**
 * 简历优化页面 - 与 Dashboard 完全一致的 Glassmorphism 风格
 * 设计原则：
 * 1. 使用 glass-card 类保持视觉一致性
 * 2. Sky 色系主题（不是 indigo/purple）
 * 3. 清晰的 3 步流程引导
 * 4. 响应式设计 + 暗黑模式支持
 */

type Step = 'upload' | 'info' | 'optimize';

interface StepConfig {
  id: Step;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
}

const ResumeOptimizerPage: React.FC = () => {
  const { token } = useAuthStore();
  const [currentStep, setCurrentStep] = useState<Step>('upload');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [optimizedPdf, setOptimizedPdf] = useState<string | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [feedback, setFeedback] = useState('');  // 反馈意见
  const [lastPdfPath, setLastPdfPath] = useState('');  // 保存上次生成的路径

  // 表单数据
  const [formData, setFormData] = useState({
    isPermanentResident: false,
    canStartImmediately: false,
    linkedinUrl: '',
    githubUrl: '',
    portfolioUrl: '',
    additionalNotes: ''  // 新增：额外要求
  });

  // 步骤配置
  const steps: StepConfig[] = [
    {
      id: 'upload',
      title: '上传简历',
      subtitle: '支持 PDF 格式，最大 10MB',
      icon: <Upload className="w-6 h-6" />
    },
    {
      id: 'info',
      title: '补充信息',
      subtitle: '完善个人资料，提升匹配度',
      icon: <FileText className="w-6 h-6" />
    },
    {
      id: 'optimize',
      title: 'AI 优化',
      subtitle: '智能优化简历内容',
      icon: <Sparkles className="w-6 h-6" />
    }
  ];

  const currentStepIndex = steps.findIndex(s => s.id === currentStep);
  const progressPercent = ((currentStepIndex + 1) / steps.length) * 100;

  // 文件上传处理
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setResumeFile(e.target.files[0]);
    }
  };

  // 优化简历
  const handleOptimize = async () => {
    if (!resumeFile) {
      alert('请先上传简历');
      return;
    }

    if (!token) {
      alert('请先登录');
      return;
    }

    setIsOptimizing(true);
    try {
      // 🔴 使用 resumeOptimizerAPI 并传递 token（和 DashboardPage 一样的方式）
      const result = await resumeOptimizerAPI.optimizeResume({
        resume_file: resumeFile,
        permanent_resident: formData.isPermanentResident,
        available_immediately: formData.canStartImmediately,
        linkedin_url: formData.linkedinUrl,
        github_url: formData.githubUrl,
        portfolio_url: formData.portfolioUrl,
        additional_notes: formData.additionalNotes
      }, token);

      // 🔴 用 blob URL 方式获取 PDF（带认证）
      const filename = result.pdf_path.split('/').pop() || '';
      setLastPdfPath(result.pdf_path);  // 保存路径用于反馈重优化
      const pdfBlob = await resumeOptimizerAPI.downloadResume(encodeURIComponent(filename), token);
      const blobUrl = URL.createObjectURL(pdfBlob);
      setOptimizedPdf(blobUrl);
    } catch (error: any) {
      console.error('优化失败:', error);
      alert(error.message || '简历优化失败，请重试');
    } finally {
      setIsOptimizing(false);
    }
  };

  // 下一步
  const goNext = () => {
    if (currentStepIndex < steps.length - 1) {
      setCurrentStep(steps[currentStepIndex + 1].id);
    }
  };

  // 上一步
  const goPrev = () => {
    if (currentStepIndex > 0) {
      setCurrentStep(steps[currentStepIndex - 1].id);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      
      {/* 页面标题 */}
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold text-gradient">
          AI 简历优化
        </h1>
        <p className="text-sky-600 dark:text-sky-400">
          让 AI 帮你打造完美简历，提升面试机会
        </p>
      </div>

      {/* 进度条卡片 */}
      <div className="glass-card p-6 animate-slide-down">
        {/* 步骤指示器 */}
        <div className="flex items-center justify-between mb-4">
          {steps.map((step, index) => (
            <React.Fragment key={step.id}>
              <div className="flex items-center space-x-3">
                {/* 步骤图标 */}
                <div
                  className={`
                    w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300
                    ${index <= currentStepIndex
                      ? 'bg-gradient-to-r from-sky-500 to-cyan-500 text-white shadow-lg shadow-sky-500/30'
                      : 'bg-sky-100 dark:bg-slate-700 text-sky-400 dark:text-slate-400'
                    }
                  `}
                >
                  {index < currentStepIndex ? (
                    <Check className="w-6 h-6" />
                  ) : (
                    step.icon
                  )}
                </div>
                
                {/* 步骤文字（桌面端显示） */}
                <div className="hidden md:block">
                  <div className={`font-semibold ${index <= currentStepIndex ? 'text-sky-700 dark:text-sky-300' : 'text-sky-400 dark:text-slate-500'}`}>
                    {step.title}
                  </div>
                  <div className="text-xs text-sky-500 dark:text-slate-400">
                    {step.subtitle}
                  </div>
                </div>
              </div>

              {/* 连接线 */}
              {index < steps.length - 1 && (
                <div className="flex-1 h-1 mx-4 bg-sky-100 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full bg-gradient-to-r from-sky-500 to-cyan-500 transition-all duration-500 ${
                      index < currentStepIndex ? 'w-full' : 'w-0'
                    }`}
                  />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* 进度百分比 */}
        <div className="text-center text-sm text-sky-600 dark:text-sky-400 font-medium">
          进度: {Math.round(progressPercent)}%
        </div>
      </div>

      {/* 步骤内容卡片 */}
      <div className="glass-card p-8 animate-fade-in">
        
        {/* Step 1: 上传简历 */}
        {currentStep === 'upload' && (
          <div className="space-y-6">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto bg-gradient-to-r from-sky-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-500/30 mb-4">
                <Upload className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">
                上传你的简历
              </h2>
              <p className="text-sky-600 dark:text-sky-400">
                支持 PDF 格式，文件大小不超过 10MB
              </p>
            </div>

            {/* 拖拽上传区域 */}
            <div
              className={`
                relative border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer
                ${resumeFile
                  ? 'border-green-400 dark:border-green-500 bg-green-50/50 dark:bg-green-900/20'
                  : 'border-sky-300 dark:border-sky-600 hover:border-sky-500 dark:hover:border-sky-400 hover:bg-sky-50/30 dark:hover:bg-sky-900/10'
                }
              `}
              onClick={() => document.getElementById('fileInput')?.click()}
            >
              <input
                id="fileInput"
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileUpload}
              />
              
              {resumeFile ? (
                <div className="space-y-3">
                  <FileText className="w-12 h-12 mx-auto text-green-600 dark:text-green-400" />
                  <div>
                    <div className="font-medium text-sky-800 dark:text-sky-200">{resumeFile.name}</div>
                    <div className="text-sm text-sky-600 dark:text-sky-400">
                      {(resumeFile.size / 1024 / 1024).toFixed(2)} MB
                    </div>
                  </div>
                  <button
                    className="text-sm text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 underline font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      setResumeFile(null);
                    }}
                  >
                    重新上传
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Upload className="w-12 h-12 mx-auto text-sky-400 dark:text-sky-500" />
                  <div>
                    <div className="text-lg font-medium text-sky-700 dark:text-sky-300">
                      点击或拖拽文件到这里
                    </div>
                    <div className="text-sm text-sky-500 dark:text-sky-400 mt-1">
                      支持的格式：PDF
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 示例提示 */}
            <div className="bg-sky-50/50 dark:bg-sky-900/20 rounded-lg p-4 border border-sky-200/60 dark:border-sky-700/60">
              <div className="flex items-start space-x-3">
                <Sparkles className="w-5 h-5 text-sky-600 dark:text-sky-400 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-sky-700 dark:text-sky-300">
                  <strong>提示：</strong>简历内容越详细，AI 优化效果越好。建议包含工作经验、教育背景、技能等信息。
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: 填写信息 */}
        {currentStep === 'info' && (
          <div className="space-y-6">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto bg-gradient-to-r from-sky-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-500/30 mb-4">
                <FileText className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">
                完善个人信息
              </h2>
              <p className="text-sky-600 dark:text-sky-400">
                这些信息将帮助 AI 更好地优化你的简历
              </p>
            </div>

            {/* 表单区域 */}
            <div className="space-y-5">
              
              {/* 切换开关 */}
              <div className="space-y-3">
                <label className="flex items-center justify-between p-4 bg-white/60 dark:bg-slate-800/60 rounded-lg border border-sky-200/60 dark:border-slate-600/60 hover:border-sky-300 dark:hover:border-sky-500 transition-colors cursor-pointer group">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-r from-green-500 to-emerald-500 flex items-center justify-center shadow-md">
                      <Check className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <div className="font-medium text-sky-800 dark:text-sky-200">永久居民身份</div>
                      <div className="text-sm text-sky-600 dark:text-sky-400">是否拥有工作签证或绿卡</div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    className="toggle toggle-sky"
                    checked={formData.isPermanentResident}
                    onChange={(e) => setFormData({ ...formData, isPermanentResident: e.target.checked })}
                  />
                </label>

                <label className="flex items-center justify-between p-4 bg-white/60 dark:bg-slate-800/60 rounded-lg border border-sky-200/60 dark:border-slate-600/60 hover:border-sky-300 dark:hover:border-sky-500 transition-colors cursor-pointer group">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-r from-sky-500 to-cyan-500 flex items-center justify-center shadow-md">
                      <Check className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <div className="font-medium text-sky-800 dark:text-sky-200">立即上班</div>
                      <div className="text-sm text-sky-600 dark:text-sky-400">是否可以随时开始工作</div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    className="toggle toggle-sky"
                    checked={formData.canStartImmediately}
                    onChange={(e) => setFormData({ ...formData, canStartImmediately: e.target.checked })}
                  />
                </label>
              </div>

              {/* URL 输入框 */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                    LinkedIn 个人主页
                  </label>
                  <input
                    type="url"
                    placeholder="https://linkedin.com/in/yourprofile"
                    className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 dark:focus:ring-sky-400 focus:border-transparent transition-all"
                    value={formData.linkedinUrl}
                    onChange={(e) => setFormData({ ...formData, linkedinUrl: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                    GitHub 主页
                  </label>
                  <input
                    type="url"
                    placeholder="https://github.com/yourusername"
                    className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 dark:focus:ring-sky-400 focus:border-transparent transition-all"
                    value={formData.githubUrl}
                    onChange={(e) => setFormData({ ...formData, githubUrl: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                    个人作品集
                  </label>
                  <input
                    type="url"
                    placeholder="https://yourportfolio.com"
                    className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 dark:focus:ring-sky-400 focus:border-transparent transition-all"
                    value={formData.portfolioUrl}
                    onChange={(e) => setFormData({ ...formData, portfolioUrl: e.target.value })}
                  />
                </div>

                {/* 额外要求 */}
                <div>
                  <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                    优化要求 <span className="text-sky-400 dark:text-slate-500 font-normal">(可选)</span>
                  </label>
                  <textarea
                    placeholder="例如：突出我的数据分析技能、删除实习经历、添加项目经验描述..."
                    rows={3}
                    className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 dark:focus:ring-sky-400 focus:border-transparent transition-all resize-none"
                    value={formData.additionalNotes}
                    onChange={(e) => setFormData({ ...formData, additionalNotes: e.target.value })}
                  />
                  <p className="text-xs text-sky-500 dark:text-slate-400 mt-1">
                    告诉 AI 你希望如何优化简历，例如突出某些技能、删除某些内容等
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: AI 优化 */}
        {currentStep === 'optimize' && (
          <div className="space-y-6">
            {!optimizedPdf ? (
              // 优化前
              <div className="text-center space-y-6">
                <div className="w-16 h-16 mx-auto bg-gradient-to-r from-sky-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-500/30">
                  <Sparkles className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">
                    准备就绪！
                  </h2>
                  <p className="text-sky-600 dark:text-sky-400">
                    AI 将分析你的简历，优化关键词、格式和内容结构
                  </p>
                </div>

                {/* 优化功能列表 */}
                <div className="grid md:grid-cols-3 gap-4 text-left">
                  {[
                    { icon: '🎯', title: '关键词优化', desc: 'ATS 系统友好' },
                    { icon: '✨', title: '格式美化', desc: '专业排版布局' },
                    { icon: '📊', title: '内容强化', desc: '突出核心优势' }
                  ].map((item, index) => (
                    <div key={index} className="bg-white/60 dark:bg-slate-800/60 rounded-lg p-4 border border-sky-200/60 dark:border-slate-600/60">
                      <div className="text-3xl mb-2">{item.icon}</div>
                      <div className="font-medium text-sky-800 dark:text-sky-200">{item.title}</div>
                      <div className="text-sm text-sky-600 dark:text-sky-400">{item.desc}</div>
                    </div>
                  ))}
                </div>

                {/* 开始优化按钮 */}
                <button
                  onClick={handleOptimize}
                  disabled={isOptimizing}
                  className="px-8 py-4 bg-gradient-to-r from-sky-500 to-cyan-500 text-white rounded-lg font-semibold hover:from-sky-600 hover:to-cyan-600 transition-all shadow-lg shadow-sky-500/30 hover:shadow-xl hover:shadow-sky-500/40 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isOptimizing ? (
                    <span className="flex items-center space-x-2">
                      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>AI 优化中...</span>
                    </span>
                  ) : (
                    '开始 AI 优化'
                  )}
                </button>
              </div>
            ) : (
              // 优化完成
              <div className="space-y-6">
                {/* 成功提示 */}
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center mb-4 shadow-lg shadow-green-500/30">
                    <Check className="w-8 h-8 text-white" />
                  </div>
                  <h2 className="text-2xl font-bold text-sky-800 dark:text-sky-200 mb-2">
                    优化完成！
                  </h2>
                  <p className="text-sky-600 dark:text-sky-400">
                    预览简历，如有需要可以提交反馈重新优化
                  </p>
                </div>

                {/* PDF 预览 */}
                <div className="bg-sky-100/50 dark:bg-slate-700/50 rounded-lg p-4 border-2 border-sky-200/60 dark:border-slate-600/60">
                  <iframe
                    src={optimizedPdf}
                    className="w-full h-[500px] rounded-lg"
                    title="优化后的简历"
                  />
                </div>

                {/* 反馈区域 */}
                <div className="bg-white/60 dark:bg-slate-800/60 rounded-lg p-4 border border-sky-200/60 dark:border-slate-600/60">
                  <label className="block text-sm font-medium text-sky-700 dark:text-sky-300 mb-2">
                    💬 反馈意见（可选）
                  </label>
                  <textarea
                    placeholder="例如：第一页太空了，第二页太满了，帮我调整一下排版..."
                    rows={3}
                    className="w-full px-4 py-3 rounded-lg border border-sky-200/60 dark:border-slate-600/60 bg-white/60 dark:bg-slate-800/60 text-sky-800 dark:text-sky-200 placeholder-sky-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 dark:focus:ring-sky-400 focus:border-transparent transition-all resize-none"
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                  />
                </div>

                {/* 操作按钮 */}
                <div className="flex flex-col sm:flex-row gap-3">
                  <a
                    href={optimizedPdf}
                    download="optimized_resume.pdf"
                    className="flex-1 py-3 bg-gradient-to-r from-sky-500 to-cyan-500 text-white rounded-lg font-semibold hover:from-sky-600 hover:to-cyan-600 transition-all shadow-lg shadow-sky-500/30 hover:shadow-xl hover:shadow-sky-500/40 text-center flex items-center justify-center space-x-2"
                  >
                    <Download className="w-5 h-5" />
                    <span>下载简历</span>
                  </a>
                  <button
                    onClick={async () => {
                      if (!feedback.trim()) {
                        alert('请先输入反馈意见');
                        return;
                      }
                      // 将反馈作为新的优化要求，重新优化
                      setFormData(prev => ({
                        ...prev,
                        additionalNotes: feedback
                      }));
                      setOptimizedPdf(null);
                      setFeedback('');
                      // 自动触发优化
                      setIsOptimizing(true);
                      try {
                        const result = await resumeOptimizerAPI.optimizeResume({
                          resume_file: resumeFile!,
                          permanent_resident: formData.isPermanentResident,
                          available_immediately: formData.canStartImmediately,
                          linkedin_url: formData.linkedinUrl,
                          github_url: formData.githubUrl,
                          portfolio_url: formData.portfolioUrl,
                          additional_notes: feedback  // 使用反馈作为新的优化要求
                        }, token!);
                        const filename = result.pdf_path.split('/').pop() || '';
                        setLastPdfPath(result.pdf_path);
                        const pdfBlob = await resumeOptimizerAPI.downloadResume(encodeURIComponent(filename), token!);
                        const blobUrl = URL.createObjectURL(pdfBlob);
                        setOptimizedPdf(blobUrl);
                      } catch (error: any) {
                        console.error('重新优化失败:', error);
                        alert(error.message || '重新优化失败，请重试');
                      } finally {
                        setIsOptimizing(false);
                      }
                    }}
                    disabled={isOptimizing}
                    className="px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-lg font-semibold hover:from-amber-600 hover:to-orange-600 transition-all shadow-lg shadow-amber-500/30 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                  >
                    {isOptimizing ? (
                      <>
                        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>优化中...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-5 h-5" />
                        <span>根据反馈重新优化</span>
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setOptimizedPdf(null);
                      setCurrentStep('upload');
                      setResumeFile(null);
                      setFeedback('');
                    }}
                    className="px-6 py-3 bg-white/60 dark:bg-slate-800/60 border border-sky-200/60 dark:border-slate-600/60 text-sky-700 dark:text-sky-300 rounded-lg font-medium hover:bg-white/80 dark:hover:bg-slate-700/80 transition-all"
                  >
                    上传新简历
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

      </div>

      {/* 底部导航按钮 */}
      {!optimizedPdf && (
        <div className="flex justify-between">
          <button
            onClick={goPrev}
            disabled={currentStepIndex === 0}
            className="px-6 py-3 bg-white/60 dark:bg-slate-800/60 border border-sky-200/60 dark:border-slate-600/60 text-sky-700 dark:text-sky-300 rounded-lg font-medium hover:bg-white/80 dark:hover:bg-slate-700/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            <ChevronLeft className="w-5 h-5" />
            <span>上一步</span>
          </button>

          <button
            onClick={goNext}
            disabled={
              (currentStep === 'upload' && !resumeFile) ||
              currentStepIndex === steps.length - 1
            }
            className="px-6 py-3 bg-gradient-to-r from-sky-500 to-cyan-500 text-white rounded-lg font-semibold hover:from-sky-600 hover:to-cyan-600 transition-all shadow-lg shadow-sky-500/30 hover:shadow-xl hover:shadow-sky-500/40 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            <span>下一步</span>
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      )}

      <style>{`
        /* Toggle Switch 样式 - Sky 主题 */
        .toggle {
          appearance: none;
          width: 3rem;
          height: 1.5rem;
          background-color: #e0f2fe;
          border-radius: 9999px;
          position: relative;
          cursor: pointer;
          transition: background-color 0.3s;
        }

        .dark .toggle {
          background-color: #334155;
        }

        .toggle:checked {
          background-color: #0ea5e9;
        }

        .dark .toggle:checked {
          background-color: #38bdf8;
        }

        .toggle::before {
          content: '';
          position: absolute;
          width: 1.25rem;
          height: 1.25rem;
          background-color: white;
          border-radius: 9999px;
          top: 0.125rem;
          left: 0.125rem;
          transition: transform 0.3s;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .toggle:checked::before {
          transform: translateX(1.5rem);
        }
      `}</style>
    </div>
  );
};

export default ResumeOptimizerPage;
