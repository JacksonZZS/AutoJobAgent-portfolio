# core/apply/hud_mixin.py
"""HUD (Heads-Up Display) mixin for JobsDBApplyBot."""

import json
import time
import logging
from pathlib import Path
from typing import Optional

from core.interaction_manager import get_interaction_manager

logger = logging.getLogger(__name__)


class HUDMixin:
    """Handles browser HUD overlay, captcha detection, and captcha resolution."""

    def _update_hud(self, message: str, status: str = "info", resume_path: Optional[str] = None, cl_path: Optional[str] = None):
        """
        在浏览器页面右上角注入/更新悬浮面板 (HUD)
        """
        status_colors = {
            "info": "#3b82f6",
            "processing": "#eab308",
            "success": "#22c55e",
            "error": "#ef4444"
        }

        color = status_colors.get(status, status_colors["info"])

        buttons = []
        if resume_path:
            resume_uri = self._get_file_as_data_uri(resume_path)
            resume_filename = Path(resume_path).name
            buttons.append({
                "label": "📄 下载定制简历 (PDF)",
                "uri": resume_uri,
                "filename": resume_filename
            })
        if cl_path:
            cl_uri = self._get_file_as_data_uri(cl_path)
            cl_filename = Path(cl_path).name
            buttons.append({
                "label": "📝 下载求职信 (PDF)",
                "uri": cl_uri,
                "filename": cl_filename
            })

        js_data = json.dumps({
            "message": message,
            "color": color,
            "buttons": buttons
        })

        js_code = f"""
        (() => {{
            const data = {js_data};
            let hud = document.getElementById('auto-job-agent-hud');

            if (!hud) {{
                hud = document.createElement('div');
                hud.id = 'auto-job-agent-hud';
                hud.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                    background: rgba(0, 0, 0, 0.85);
                    color: white;
                    padding: 16px 24px;
                    border-radius: 8px;
                    font-size: 18px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-weight: 500;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                    max-width: 400px;
                    word-wrap: break-word;
                    transition: all 0.3s ease;
                `;
                document.body.appendChild(hud);
            }}

            let html = '<div style="margin-bottom:5px">' + data.message + '</div>';
            data.buttons.forEach(btn => {{
                html += `<a href="${{btn.uri}}" download="${{btn.filename}}" style="display:block; margin-top:8px; background:white; color:#333; padding:10px 16px; text-decoration:none; border-radius:6px; font-weight:600; text-align:center; font-size:14px;">${{btn.label}}</a>`;
            }});

            hud.innerHTML = html;
            hud.style.borderLeft = '4px solid ' + data.color;

            hud.style.opacity = '0';
            hud.style.transform = 'translateX(20px)';
            setTimeout(() => {{
                hud.style.opacity = '1';
                hud.style.transform = 'translateX(0)';
            }}, 10);
        }})();
        """

        try:
            if self._page:
                self._page.evaluate(js_code)
                logger.debug(f"HUD updated: [{status}] {message}")
        except Exception as e:
            logger.warning(f"Failed to update HUD: {e}")

    def _check_captcha(self) -> bool:
        """检查是否出现验证码"""
        try:
            captcha = self._page.query_selector(self.selectors["captcha_indicator"])
            return captcha is not None
        except:
            return False

    def _wait_for_captcha_resolution(self):
        """
        等待用户手动处理验证码
        """
        if not self.allow_manual_captcha:
            logger.error("Captcha detected but manual resolution is disabled")
            raise RuntimeError("Captcha detected but manual resolution is not allowed")

        logger.warning("=" * 50)
        logger.warning("Captcha detected! Please complete it in the browser.")
        logger.warning(f"Waiting for user to complete captcha (timeout: {self.captcha_timeout}s)...")
        logger.warning("=" * 50)

        interaction_mgr = get_interaction_manager(user_id=self.user_id)

        if hasattr(self, 'status_manager') and self.status_manager:
            self.status_manager.update(
                status="waiting_user",
                message="检测到验证码，请在浏览器中完成验证",
                step="captcha_waiting"
            )

        start_time = time.time()

        try:
            success = interaction_mgr.wait_for_user_action(
                message="请在浏览器中完成验证码验证",
                timeout=self.captcha_timeout
            )

            elapsed = time.time() - start_time

            if not success:
                logger.error(f"Captcha resolution timeout or cancelled ({elapsed:.1f}s)")
                raise TimeoutError(f"Captcha resolution timeout after {elapsed:.1f}s")

            logger.info(f"Captcha resolution completed in {elapsed:.1f}s")
            time.sleep(2)

        except KeyboardInterrupt:
            logger.warning("Captcha resolution interrupted by user")
            raise
