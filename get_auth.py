import os
from playwright.sync_api import sync_playwright

def save_auth_state():
    """
    使用电脑上真实的 Chrome 浏览器 + 持久化配置文件夹
    """
    # 这里我们不再只存一个 auth.json，而是存整个浏览器配置文件夹
    user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
    
    print(f"📂 浏览器配置文件将保存在: {user_data_dir}")

    with sync_playwright() as p:
        print("🚀 正在启动真实的 Google Chrome...")
        
        try:
            # 👇 核心黑科技：launch_persistent_context
            # channel="chrome" 会强制使用你 Mac 里安装的谷歌浏览器
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",  # 👈 指定使用真实 Chrome
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox', 
                ],
                viewport={'width': 1280, 'height': 800}
            )
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            print("请确认你的 Mac 上安装了 Google Chrome 浏览器！")
            return

        page = context.pages[0]
        
        # 再次注入反爬补丁，双重保险
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🌍 正在打开 JobsDB...")
        page.goto("https://hk.jobsdb.com/hk")
        
        print("\n" + "="*50)
        print("👉 请在弹出的 Chrome 窗口中操作：")
        print("1. 如果没登录，请点击右上角登录。")
        print("2. ⚠️ 关键步骤：请手动在搜索框试着搜一下 'Data Analyst'。")
        print("3. 如果能看到职位列表（没有报错），说明我们成功了！")
        print("4. 确认一切正常后，关闭浏览器窗口，然后回到这里按【回车】。")
        print("="*50 + "\n")
        
        input("Waiting... (操作完成后按回车结束)")
        
        context.close()
        print("✅ 配置文件已保存，Server 可以使用了！")

if __name__ == "__main__":
    save_auth_state()