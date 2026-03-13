"""
邮件服务 - 支持 SMTP 发送邮件
支持 Gmail / QQ邮箱 / 163 等
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Optional, List, Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import asyncio
from functools import partial


class EmailService:
    """邮件服务封装"""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_name = os.getenv("SMTP_FROM_NAME", "AutoJob Agent")
        self.enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        
        # Jinja2 模板环境
        template_dir = Path(__file__).parent.parent / "templates" / "email"
        if template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=True
            )
        else:
            self.jinja_env = None
    
    def _create_connection(self) -> smtplib.SMTP:
        """创建 SMTP 连接"""
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()
        server.login(self.smtp_user, self.smtp_password)
        return server
    
    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """渲染 Jinja2 模板"""
        if not self.jinja_env:
            return f"<html><body><p>{context}</p></body></html>"
        
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)
    
    async def send_email(
        self,
        to: str,
        subject: str,
        template: str,
        context: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        发送邮件
        
        Args:
            to: 收件人邮箱
            subject: 邮件主题
            template: 模板文件名 (如 job_alert.html)
            context: 模板变量
            attachments: 附件列表 [{"filename": "resume.pdf", "content": bytes}]
        
        Returns:
            bool: 是否发送成功
        """
        if not self.enabled:
            print(f"[EmailService] 邮件未启用，跳过发送: {subject}")
            return False
        
        if not self.smtp_user or not self.smtp_password:
            print("[EmailService] SMTP 配置不完整")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.smtp_user}>"
            msg["To"] = to
            
            # 渲染 HTML 内容
            html_content = self._render_template(template, context)
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            
            # 添加附件
            if attachments:
                for attachment in attachments:
                    part = MIMEApplication(
                        attachment["content"],
                        Name=attachment["filename"]
                    )
                    part["Content-Disposition"] = f'attachment; filename="{attachment["filename"]}"'
                    msg.attach(part)
            
            # 异步发送
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(self._send_sync, msg, to)
            )
            
            print(f"[EmailService] 邮件发送成功: {to}")
            return True
            
        except Exception as e:
            print(f"[EmailService] 邮件发送失败: {e}")
            return False
    
    def _send_sync(self, msg: MIMEMultipart, to: str):
        """同步发送（在线程池中执行）"""
        with self._create_connection() as server:
            server.sendmail(self.smtp_user, to, msg.as_string())
    
    async def send_job_alert(
        self,
        user_email: str,
        user_name: str,
        jobs: List[Dict[str, Any]],
        min_score: int = 80
    ) -> bool:
        """
        发送高分职位通知
        
        Args:
            user_email: 用户邮箱
            user_name: 用户姓名
            jobs: 职位列表
            min_score: 最低匹配分数
        """
        # 过滤高分职位
        high_score_jobs = [j for j in jobs if j.get("match_score", 0) >= min_score]
        
        if not high_score_jobs:
            return False
        
        context = {
            "user_name": user_name,
            "jobs": high_score_jobs,
            "job_count": len(high_score_jobs),
            "min_score": min_score
        }
        
        return await self.send_email(
            to=user_email,
            subject=f"🎯 发现 {len(high_score_jobs)} 个高匹配职位！",
            template="job_alert.html",
            context=context
        )
    
    async def send_follow_up(
        self,
        user_email: str,
        user_name: str,
        job: Dict[str, Any],
        content: str,
        recipient_email: str,
        recipient_name: str
    ) -> bool:
        """
        发送跟进邮件
        
        Args:
            user_email: 用户邮箱（抄送）
            user_name: 用户姓名
            job: 职位信息
            content: AI 生成的邮件内容
            recipient_email: HR 邮箱
            recipient_name: HR 姓名
        """
        context = {
            "user_name": user_name,
            "recipient_name": recipient_name,
            "job_title": job.get("title", ""),
            "company": job.get("company", ""),
            "content": content
        }
        
        return await self.send_email(
            to=recipient_email,
            subject=f"关于 {job.get('title', '')} 职位申请 - {user_name}",
            template="follow_up.html",
            context=context
        )
    
    async def send_thank_you(
        self,
        user_email: str,
        user_name: str,
        job: Dict[str, Any],
        content: str,
        recipient_email: str,
        recipient_name: str
    ) -> bool:
        """
        发送感谢信
        """
        context = {
            "user_name": user_name,
            "recipient_name": recipient_name,
            "job_title": job.get("title", ""),
            "company": job.get("company", ""),
            "content": content
        }
        
        return await self.send_email(
            to=recipient_email,
            subject=f"感谢您的时间 - {user_name}",
            template="thank_you.html",
            context=context
        )


# 单例
email_service = EmailService()
