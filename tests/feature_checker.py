#!/usr/bin/env python3
"""
AutoJobAgent 功能自动化检查脚本
使用 rich 库输出美观的测试结果
"""

import argparse
import sys
import time
from typing import Dict, Any, Optional, Tuple
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from datetime import datetime
import json

console = Console()


class FeatureChecker:
    """功能检查器"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.results: list[Tuple[str, bool, str, float]] = []
        
    def check_feature(self, name: str, method: str, endpoint: str, 
                     data: Optional[Dict] = None, 
                     auth_required: bool = False) -> Tuple[bool, str, float]:
        """
        检查单个功能
        
        Returns:
            (成功, 错误信息, 响应时间)
        """
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if auth_required and self.token:
            headers['Authorization'] = f"Bearer {self.token}"
        
        try:
            start_time = time.time()
            
            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers, timeout=10)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, headers=headers, timeout=10)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, headers=headers, timeout=10)
            else:
                return False, f"不支持的 HTTP 方法: {method}", 0
            
            elapsed = time.time() - start_time
            
            # 检查响应状态
            if response.status_code == 200:
                return True, f"HTTP {response.status_code}", elapsed
            elif response.status_code == 401:
                return False, "未授权 (401)", elapsed
            elif response.status_code == 404:
                return False, "未找到 (404)", elapsed
            elif response.status_code == 500:
                return False, f"服务器错误 (500): {response.text[:100]}", elapsed
            else:
                return False, f"HTTP {response.status_code}", elapsed
                
        except requests.exceptions.ConnectionError:
            return False, "连接失败 - 服务器未运行", 0
        except requests.exceptions.Timeout:
            return False, "请求超时", 10.0
        except Exception as e:
            return False, f"异常: {str(e)[:50]}", 0
    
    def login(self) -> bool:
        """执行登录并获取 token"""
        console.print("\n[bold cyan]🔐 执行登录...[/bold cyan]")
        
        success, message, elapsed = self.check_feature(
            "登录",
            "POST",
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password}
        )
        
        if success:
            # 尝试从响应中提取 token
            try:
                response = self.session.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={"username": self.username, "password": self.password}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get('access_token') or data.get('token')
                    console.print(f"[green]✓ 登录成功 ({elapsed:.2f}s)[/green]")
                    if self.token:
                        console.print(f"[dim]Token: {self.token[:20]}...[/dim]")
                    return True
            except Exception as e:
                console.print(f"[yellow]⚠ 登录成功但无法提取 token: {e}[/yellow]")
                return True
        
        console.print(f"[red]✗ 登录失败: {message}[/red]")
        return False
    
    def run_all_checks(self):
        """运行所有功能检查"""
        
        # 显示测试信息
        info_panel = Panel(
            f"[bold]Base URL:[/bold] {self.base_url}\n"
            f"[bold]Username:[/bold] {self.username}\n"
            f"[bold]Time:[/bold] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            title="[bold cyan]AutoJobAgent 功能检查[/bold cyan]",
            border_style="cyan"
        )
        console.print(info_panel)
        
        # 定义所有检查项
        checks = [
            # 基础功能
            ("健康检查", "GET", "/health", None, False),
            ("登录", "POST", "/api/v1/auth/login", 
             {"username": self.username, "password": self.password}, False),
            
            # 需要认证的功能
            ("获取用户信息", "GET", "/api/v1/auth/me", None, True),
            ("获取任务状态", "GET", "/api/v1/jobs/status", None, True),
            ("获取投递历史", "GET", "/api/v1/history/", None, True),
            ("获取统计数据", "GET", "/api/v1/statistics/dashboard", None, True),
            ("获取收藏列表", "GET", "/api/v1/favorites/", None, True),
            ("岗位问答分类", "GET", "/api/v1/candidate-support/categories", None, True),
            ("邮件配置", "GET", "/api/v1/email/config", None, True),
            
            # 文件下载 (使用示例文件名)
            ("下载简历测试", "GET", "/api/v1/materials/download/resume/example.pdf", None, True),
        ]
        
        # 先尝试登录
        login_success = self.login()
        
        # 使用进度条显示
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            task = progress.add_task("[cyan]检查功能中...", total=len(checks))
            
            for name, method, endpoint, data, auth_required in checks:
                # 如果需要认证但登录失败，跳过
                if auth_required and not login_success:
                    self.results.append((name, False, "未登录", 0))
                    progress.advance(task)
                    continue
                
                success, message, elapsed = self.check_feature(
                    name, method, endpoint, data, auth_required
                )
                self.results.append((name, success, message, elapsed))
                progress.advance(task)
                
                # 避免请求过快
                time.sleep(0.1)
        
        # 显示结果
        self.display_results()
    
    def display_results(self):
        """显示测试结果表格"""
        
        # 创建表格
        table = Table(
            title="[bold]功能测试结果[/bold]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("状态", style="bold", width=8)
        table.add_column("功能名称", style="cyan", width=25)
        table.add_column("结果", width=35)
        table.add_column("响应时间", justify="right", width=12)
        
        success_count = 0
        fail_count = 0
        total_time = 0
        
        for name, success, message, elapsed in self.results:
            if success:
                status = "[green]✅ 正常[/green]"
                result = f"[green]{message}[/green]"
                success_count += 1
            else:
                status = "[red]❌ 失败[/red]"
                result = f"[red]{message}[/red]"
                fail_count += 1
            
            time_str = f"{elapsed:.3f}s" if elapsed > 0 else "N/A"
            total_time += elapsed
            
            table.add_row(status, name, result, time_str)
        
        console.print("\n")
        console.print(table)
        
        # 显示统计信息
        total = len(self.results)
        success_rate = (success_count / total * 100) if total > 0 else 0
        
        stats_text = (
            f"[bold]总计:[/bold] {total} 项\n"
            f"[green]成功:[/green] {success_count} 项\n"
            f"[red]失败:[/red] {fail_count} 项\n"
            f"[cyan]成功率:[/cyan] {success_rate:.1f}%\n"
            f"[yellow]总耗时:[/yellow] {total_time:.2f}s"
        )
        
        stats_panel = Panel(
            stats_text,
            title="[bold]统计信息[/bold]",
            border_style="yellow"
        )
        console.print("\n")
        console.print(stats_panel)
        
        # 返回退出码
        return 0 if fail_count == 0 else 1
    
    def export_json(self, filepath: str):
        """导出结果为 JSON"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "total": len(self.results),
            "success": sum(1 for _, success, _, _ in self.results if success),
            "failed": sum(1 for _, success, _, _ in self.results if not success),
            "results": [
                {
                    "name": name,
                    "success": success,
                    "message": message,
                    "elapsed": elapsed
                }
                for name, success, message, elapsed in self.results
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        console.print(f"\n[green]✓ 结果已导出到: {filepath}[/green]")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AutoJobAgent 功能自动化检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tests/feature_checker.py --url http://localhost:8000 --username demo --password demo123
  python tests/feature_checker.py --url https://api.example.com --username admin --password admin123 --export results.json
        """
    )
    
    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='API 基础 URL (默认: http://localhost:8000)'
    )
    
    parser.add_argument(
        '--username',
        default='demo',
        help='登录用户名 (默认: demo)'
    )
    
    parser.add_argument(
        '--password',
        default='demo123',
        help='登录密码 (默认: demo123)'
    )
    
    parser.add_argument(
        '--export',
        metavar='FILE',
        help='导出结果到 JSON 文件'
    )
    
    args = parser.parse_args()
    
    # 创建检查器
    checker = FeatureChecker(args.url, args.username, args.password)
    
    try:
        # 运行检查
        checker.run_all_checks()
        
        # 导出结果
        if args.export:
            checker.export_json(args.export)
        
        # 返回退出码
        sys.exit(checker.display_results())
        
    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠ 用户中断[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]✗ 错误: {e}[/red]", style="bold")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
