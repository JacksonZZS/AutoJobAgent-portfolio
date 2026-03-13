/**
 * AutoJob Agent Chrome Extension - Content Script
 * 在职位页面上运行，添加快捷抓取按钮
 */

(function() {
  // 防止重复注入
  if (window.__autojob_injected) return;
  window.__autojob_injected = true;
  
  // 创建浮动按钮
  const floatBtn = document.createElement('div');
  floatBtn.id = 'autojob-float-btn';
  floatBtn.innerHTML = `
    <div style="
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 56px;
      height: 56px;
      background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4);
      z-index: 999999;
      transition: all 0.3s ease;
    " onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
      <span style="font-size: 24px;">🎯</span>
    </div>
  `;
  
  document.body.appendChild(floatBtn);
  
  // 点击发送到扩展
  floatBtn.addEventListener('click', () => {
    // 发送消息到 popup
    chrome.runtime.sendMessage({ action: 'extractJob' });
    
    // 显示提示
    showToast('请打开扩展查看抓取结果');
  });
  
  // Toast 提示
  function showToast(message) {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      bottom: 90px;
      right: 20px;
      background: #0c4a6e;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 14px;
      z-index: 999999;
      animation: fadeIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 2000);
  }
  
  console.log('✅ AutoJob Agent content script loaded');
})();
