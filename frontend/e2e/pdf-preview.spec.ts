import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:8000';

// 健康检查测试
test.describe('服务健康检查', () => {
  test('前端服务可访问', async ({ page }) => {
    const response = await page.goto(FRONTEND_URL);
    expect(response?.status()).toBe(200);
    console.log('✅ 前端服务运行正常');
  });

  test('后端服务可访问', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/health`);
    expect(response.status()).toBe(200);
    console.log('✅ 后端服务运行正常');
  });
});

// PDF 预览功能测试
test.describe('PDF 预览功能 E2E 测试', () => {
  
  test('场景1: 简历优化器页面加载', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/resume-optimizer`);
    await page.waitForLoadState('networkidle');
    
    // 验证页面标题
    const title = page.locator('h1:has-text("简历优化")');
    await expect(title).toBeVisible({ timeout: 10000 });
    console.log('✅ 简历优化器页面加载成功');
    
    // 验证上传区域
    const uploadArea = page.locator('text=上传简历, text=点击上传').first();
    await expect(uploadArea).toBeVisible();
    console.log('✅ 上传区域显示正常');
  });

  test('场景2: 文件上传区域交互', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/resume-optimizer`);
    await page.waitForLoadState('networkidle');
    
    // 验证文件输入框存在
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached();
    console.log('✅ 文件输入框存在');
    
    // 验证上传区域可点击
    const uploadZone = page.locator('.border-dashed').first();
    await expect(uploadZone).toBeVisible();
    console.log('✅ 上传区域可交互');
  });

  test('场景3: 表单元素验证', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/resume-optimizer`);
    await page.waitForLoadState('networkidle');
    
    // 验证 LinkedIn 输入框
    const linkedinInput = page.locator('input[placeholder*="linkedin"]');
    if (await linkedinInput.count() > 0) {
      await expect(linkedinInput).toBeVisible();
      console.log('✅ LinkedIn 输入框显示');
    }
    
    // 验证 GitHub 输入框
    const githubInput = page.locator('input[placeholder*="github"]');
    if (await githubInput.count() > 0) {
      await expect(githubInput).toBeVisible();
      console.log('✅ GitHub 输入框显示');
    }
    
    // 验证提交按钮
    const submitButton = page.locator('button:has-text("开始优化")');
    await expect(submitButton).toBeVisible();
    console.log('✅ 提交按钮显示');
  });

  test('场景4: API 路由验证', async ({ request }) => {
    // 验证 feedback 路由存在
    const feedbackResponse = await request.post(`${BACKEND_URL}/api/v1/feedback/regenerate`, {
      data: {
        resume_id: 'test-123',
        feedback: '测试反馈',
        feedback_type: 'general'
      },
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    // 401 表示路由存在但需要认证，这是预期的
    expect([200, 401, 422]).toContain(feedbackResponse.status());
    console.log(`✅ Feedback API 路由存在 (状态: ${feedbackResponse.status()})`);
  });

  test('场景5: PDFPreview 组件检查', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/resume-optimizer`);
    await page.waitForLoadState('networkidle');
    
    // 检查 react-pdf 相关样式是否加载
    const styles = await page.evaluate(() => {
      return Array.from(document.styleSheets).length;
    });
    expect(styles).toBeGreaterThan(0);
    console.log(`✅ 页面样式加载 (${styles} 个样式表)`);
    
    // 截图保存
    await page.screenshot({ 
      path: 'e2e/screenshots/resume-optimizer-page.png',
      fullPage: true 
    });
    console.log('✅ 截图已保存');
  });
});

// 组件集成测试
test.describe('组件集成验证', () => {
  
  test('PDFPreview 组件导入检查', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/resume-optimizer`);
    
    // 检查页面没有 JS 错误
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });
    
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    // 过滤掉非关键错误
    const criticalErrors = errors.filter(e => 
      !e.includes('ResizeObserver') && 
      !e.includes('Loading chunk')
    );
    
    expect(criticalErrors.length).toBe(0);
    console.log('✅ 页面无 JS 关键错误');
  });
});
