/**
 * AutoJob Agent Chrome Extension - Popup Script
 */

// 状态管理
let extractedJob = null;

// DOM 元素
const statusEl = document.getElementById('status');
const jobInfoEl = document.getElementById('jobInfo');
const jobTitleEl = document.getElementById('jobTitle');
const jobCompanyEl = document.getElementById('jobCompany');
const extractBtn = document.getElementById('extractBtn');
const sendBtn = document.getElementById('sendBtn');
const apiUrlInput = document.getElementById('apiUrl');

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  // 加载保存的 API URL
  const saved = await chrome.storage.local.get(['apiUrl']);
  if (saved.apiUrl) {
    apiUrlInput.value = saved.apiUrl;
  }
  
  // 检测当前页面
  checkCurrentPage();
});

// 保存 API URL
apiUrlInput.addEventListener('change', () => {
  chrome.storage.local.set({ apiUrl: apiUrlInput.value });
});

// 检测当前页面是否支持
async function checkCurrentPage() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tab.url;
    
    const supportedSites = [
      'linkedin.com/jobs',
      'indeed.com',
      'indeed.hk',
      'glassdoor.com',
      'jobsdb.com'
    ];
    
    const isSupported = supportedSites.some(site => url.includes(site));
    
    if (isSupported) {
      updateStatus('success', '✅ 检测到职位页面');
      extractBtn.disabled = false;
    } else {
      updateStatus('warning', '⚠️ 请在职位详情页使用');
      extractBtn.disabled = true;
    }
  } catch (error) {
    updateStatus('error', '❌ 无法检测页面');
    console.error(error);
  }
}

// 更新状态显示
function updateStatus(type, message) {
  statusEl.className = `status ${type}`;
  statusEl.innerHTML = `<span>${message}</span>`;
}

// 抓取职位信息
extractBtn.addEventListener('click', async () => {
  extractBtn.disabled = true;
  extractBtn.innerHTML = '<span class="loading"></span><span>抓取中...</span>';
  
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // 执行内容脚本抓取
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      function: extractJobInfo
    });
    
    if (results && results[0] && results[0].result) {
      extractedJob = results[0].result;
      
      // 显示抓取结果
      jobTitleEl.textContent = extractedJob.title || '未知职位';
      jobCompanyEl.textContent = extractedJob.company || '未知公司';
      jobInfoEl.style.display = 'block';
      
      updateStatus('success', '✅ 抓取成功！');
      sendBtn.style.display = 'block';
    } else {
      updateStatus('error', '❌ 未能提取职位信息');
    }
  } catch (error) {
    console.error('抓取失败:', error);
    updateStatus('error', '❌ 抓取失败');
  }
  
  extractBtn.disabled = false;
  extractBtn.innerHTML = '<span>📋</span><span>抓取职位信息</span>';
});

// 发送到后端
sendBtn.addEventListener('click', async () => {
  if (!extractedJob) return;
  
  sendBtn.disabled = true;
  sendBtn.innerHTML = '<span class="loading"></span><span>发送中...</span>';
  
  try {
    const apiUrl = apiUrlInput.value.replace(/\/$/, '');
    const token = await getAuthToken();
    
    const response = await fetch(`${apiUrl}/api/v1/jobs/import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(extractedJob)
    });
    
    if (response.ok) {
      updateStatus('success', '✅ 已发送到 AutoJob Agent！');
      sendBtn.innerHTML = '<span>✓</span><span>发送成功</span>';
    } else {
      const error = await response.json();
      updateStatus('error', `❌ ${error.detail || '发送失败'}`);
      sendBtn.innerHTML = '<span>🚀</span><span>重试发送</span>';
    }
  } catch (error) {
    console.error('发送失败:', error);
    updateStatus('error', '❌ 无法连接服务器');
    sendBtn.innerHTML = '<span>🚀</span><span>重试发送</span>';
  }
  
  sendBtn.disabled = false;
});

// 获取认证 Token
async function getAuthToken() {
  const saved = await chrome.storage.local.get(['authToken']);
  return saved.authToken || '';
}

// 职位信息抓取函数（在页面上下文中执行）
function extractJobInfo() {
  const url = window.location.href;
  let job = {
    url: url,
    title: '',
    company: '',
    location: '',
    salary: '',
    description: '',
    requirements: [],
    source: ''
  };
  
  // LinkedIn
  if (url.includes('linkedin.com')) {
    job.source = 'LinkedIn';
    job.title = document.querySelector('.job-details-jobs-unified-top-card__job-title')?.textContent?.trim() || 
                document.querySelector('.topcard__title')?.textContent?.trim() || '';
    job.company = document.querySelector('.job-details-jobs-unified-top-card__company-name')?.textContent?.trim() ||
                  document.querySelector('.topcard__org-name-link')?.textContent?.trim() || '';
    job.location = document.querySelector('.job-details-jobs-unified-top-card__bullet')?.textContent?.trim() ||
                   document.querySelector('.topcard__flavor--bullet')?.textContent?.trim() || '';
    job.description = document.querySelector('.jobs-description__content')?.textContent?.trim() ||
                      document.querySelector('.description__text')?.textContent?.trim() || '';
  }
  
  // Indeed
  else if (url.includes('indeed.com') || url.includes('indeed.hk')) {
    job.source = 'Indeed';
    job.title = document.querySelector('[data-testid="jobsearch-JobInfoHeader-title"]')?.textContent?.trim() ||
                document.querySelector('.jobsearch-JobInfoHeader-title')?.textContent?.trim() || '';
    job.company = document.querySelector('[data-testid="inlineHeader-companyName"]')?.textContent?.trim() ||
                  document.querySelector('.jobsearch-InlineCompanyRating-companyHeader')?.textContent?.trim() || '';
    job.location = document.querySelector('[data-testid="job-location"]')?.textContent?.trim() ||
                   document.querySelector('.jobsearch-JobInfoHeader-subtitle > div:last-child')?.textContent?.trim() || '';
    job.salary = document.querySelector('[data-testid="attribute_snippet_testid"]')?.textContent?.trim() || '';
    job.description = document.querySelector('#jobDescriptionText')?.textContent?.trim() || '';
  }
  
  // Glassdoor
  else if (url.includes('glassdoor.com')) {
    job.source = 'Glassdoor';
    job.title = document.querySelector('[data-test="job-title"]')?.textContent?.trim() || '';
    job.company = document.querySelector('[data-test="employerName"]')?.textContent?.trim() || '';
    job.location = document.querySelector('[data-test="location"]')?.textContent?.trim() || '';
    job.description = document.querySelector('.jobDescriptionContent')?.textContent?.trim() || '';
  }
  
  // JobsDB
  else if (url.includes('jobsdb.com')) {
    job.source = 'JobsDB';
    job.title = document.querySelector('h1[data-automation="job-detail-title"]')?.textContent?.trim() || '';
    job.company = document.querySelector('[data-automation="advertiser-name"]')?.textContent?.trim() || '';
    job.location = document.querySelector('[data-automation="job-detail-location"]')?.textContent?.trim() || '';
    job.description = document.querySelector('[data-automation="jobDescription"]')?.textContent?.trim() || '';
  }
  
  return job;
}
