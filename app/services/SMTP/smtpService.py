import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Dict, Any
from jinja2 import Template
from app.config import Config


class SMTPService:
    @staticmethod
    def send_html_email(to_email: str, subject: str, html_content: str) -> bool:
        """Send HTML email using simple Gmail SMTP pattern"""
        config = Config()
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(config.EMAIL_FROM_ADDRESS, config.SMTP_PASSWORD)
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM_ADDRESS}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        server.send_message(msg)
        server.quit()
        return True
    
    @staticmethod
    def send_template_email(
        to_email: str,
        subject: str,
        template_path: str,
        template_data: Dict[str, Any]
    ) -> bool:
        """Send email using Jinja2 HTML template"""
        with open(template_path, 'r', encoding='utf-8') as file:
            template_content = file.read()
        
        template = Template(template_content)
        html_content = template.render(**template_data)
        
        return SMTPService.send_html_email(to_email, subject, html_content)
    
    @staticmethod
    def send_followup_email(
        to_email: str,
        user_name: str,
        session_date: str,
        session_time: str,
        join_url: str,
        reschedule_url: str = None,
        cancel_url: str = None
    ) -> bool:
        """Send session followup email using the template"""
        config = Config()
        template_path = os.path.join(
            os.path.dirname(__file__), 
            'template.html'
        )
        
        template_data = {
            'hero_title': f'Pengingat Sesi 2 - Halo {user_name}!',
            'session_date': session_date,
            'session_time': session_time,
            'join_url': join_url,
            'reschedule_url': reschedule_url or 'google.com',
            'cancel_url': cancel_url or 'google.com',
            'brand_name': 'Mental Health App',
            'support_email': config.EMAIL_FROM_ADDRESS,
            'primary_color': '#0F766E'
        }
        
        subject = f'Pengingat: Sesi 2 - {session_date}'
        
        return SMTPService.send_template_email(
            to_email=to_email,
            subject=subject,
            template_path=template_path,
            template_data=template_data
        )


smtp_service = SMTPService()