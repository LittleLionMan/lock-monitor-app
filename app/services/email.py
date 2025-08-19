import smtplib
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Optional
from datetime import datetime

class EmailService:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        # Validate email configuration
        if not self._validate_config():
            raise ValueError("Email service configuration is invalid")

    def _validate_config(self) -> bool:
        required_fields = [
            'SMTP_SERVER', 'SMTP_PORT', 'EMAIL_USERNAME',
            'EMAIL_PASSWORD', 'EMAIL_FROM', 'EMAIL_FROM_NAME'
        ]

        for field in required_fields:
            if not getattr(self.config, field):
                self.logger.error(f"Missing email configuration: {field}")
                return False

        return True

    def send_strike_email(self, user_info: Dict[str, str], strike_info: Dict) -> bool:
        try:
            strike_type = strike_info.get('strike_type', 'unknown')
            is_guest_card = user_info.get('is_guest_card', False)

            if is_guest_card:
                self.logger.info(f"Sending {strike_type} email for guest card to supervisor: {user_info['supervisor']}")
                return self._send_guest_card_email(user_info, strike_info)
            else:
                self.logger.info(f"Sending {strike_type} email to {user_info['name']} with CC to supervisor")
                return self._send_user_email(user_info, strike_info)

        except Exception as e:
            self.logger.error(f"Error sending strike email: {str(e)}")
            return False

    def _send_user_email(self, user_info: Dict[str, str], strike_info: Dict) -> bool:

        try:
            user_email = user_info.get('email', '')
            supervisor_email = user_info.get('supervisor_email', '')

            if self.config.TEST_MODE and self.config.TEST_EMAIL_RECIPIENT:
                user_email = self.config.TEST_EMAIL_RECIPIENT
                supervisor_email = ''
                self.logger.info(f"TEST MODE: Redirecting email to {user_email}")

            subject, body = self._get_email_content(user_info, strike_info)

            if not subject or not body:
                return False

            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"{self.config.EMAIL_FROM_NAME} <{self.config.EMAIL_FROM}>"
            message['To'] = user_email

            if supervisor_email and not self.config.TEST_MODE:
                message['Cc'] = supervisor_email

            text_part = MIMEText(body, 'plain', 'utf-8')
            message.attach(text_part)

            recipients = [user_email]
            if supervisor_email and not self.config.TEST_MODE:
                recipients.append(supervisor_email)

            success = self._send_email_to_recipients(message, recipients)

            if success:
                self.logger.info(f"Successfully sent email to {user_info['name']} and supervisor")

            return success

        except Exception as e:
            self.logger.error(f"Error sending user email: {str(e)}")
            return False

    def _send_guest_card_email(self, user_info: Dict[str, str], strike_info: Dict) -> bool:
        try:
            supervisor_email = user_info.get('supervisor_email', '')

            if not supervisor_email:
                self.logger.error(f"No supervisor email available for guest card: {user_info['card_uid']}")
                return False

            if self.config.TEST_MODE and self.config.TEST_EMAIL_RECIPIENT:
                supervisor_email = self.config.TEST_EMAIL_RECIPIENT
                self.logger.info(f"TEST MODE: Redirecting guest card email to {supervisor_email}")

            subject, body = self._get_email_content(user_info, strike_info)

            if not subject or not body:
                return False

            message = MIMEMultipart('alternative')
            message['Subject'] = f"[Gästekarte] {subject}"
            message['From'] = f"{self.config.EMAIL_FROM_NAME} <{self.config.EMAIL_FROM}>"
            message['To'] = supervisor_email

            text_part = MIMEText(body, 'plain', 'utf-8')
            message.attach(text_part)

            success = self._send_email_to_recipients(message, [supervisor_email])

            if success:
                self.logger.info(f"Successfully sent guest card email to supervisor: {user_info['supervisor']}")

            return success

        except Exception as e:
            self.logger.error(f"Error sending guest card email: {str(e)}")
            return False

    def _get_email_content(self, user_info: Dict[str, str], strike_info: Dict) -> tuple[Optional[str], Optional[str]]:
        try:
            strike_type = strike_info.get('strike_type', 'unknown')
            is_guest_card = user_info.get('is_guest_card', False)

            if is_guest_card:
                template_file = f"email_templates/guest_card_{strike_type}.txt"
            else:
                if strike_type == 'strike_1':
                    template_key = 'strike_1'
                elif strike_type == 'strike_2':
                    template_key = 'strike_2'
                elif strike_type in ['strike_3', 'counter']:
                    template_key = 'strike_3'
                else:
                    self.logger.error(f"Unknown strike type: {strike_type}")
                    return None, None

                template_file = self.config.EMAIL_TEMPLATES[template_key]['template_file']

            content = self._load_email_template(template_file, user_info, strike_info)

            if not content:
                return None, None

            subject, body = self._extract_subject_and_body(content)

            return subject, body

        except Exception as e:
            self.logger.error(f"Error generating email content: {str(e)}")
            return None, None

    def _extract_subject_and_body(self, content: str) -> tuple[str, str]:
        lines = content.split('\n')
        subject = ""
        body_lines = []

        for i, line in enumerate(lines):
            if line.startswith('Betreff: '):
                subject = line.replace('Betreff: ', '').strip()
            elif i > 0 and not line.startswith('Betreff: '):
                body_lines.append(line)

        body = '\n'.join(body_lines).strip()
        return subject, body

    def _load_email_template(self, template_file: str, user_info: Dict[str, str], strike_info: Dict) -> Optional[str]:
        try:
            if not os.path.exists(template_file):
                self.logger.error(f"Template file not found: {template_file}")
                return None

            with open(template_file, 'r', encoding='utf-8') as f:
                template = f.read()

            processed_template = self._process_template_variables(template, user_info, strike_info)

            return processed_template

        except Exception as e:
            self.logger.error(f"Error loading email template: {str(e)}")
            return None

    def _process_template_variables(self, template: str, user_info: Dict[str, str], strike_info: Dict) -> str:
        try:
            variables = {
                '{{name}}': user_info.get('name', 'N/A'),
                '{{supervisor}}': user_info.get('supervisor', 'N/A'),
                '{{card_uid}}': user_info.get('card_uid', 'N/A'),
                '{{strike_type}}': strike_info.get('strike_type', 'N/A'),
                '{{violation_date}}': strike_info.get('violation_date', 'N/A'),
                '{{location}}': strike_info.get('location', 'N/A'),
                '{{lock_id}}': strike_info.get('lock_id', 'N/A'),
                '{{current_date}}': datetime.now().strftime('%d.%m.%Y'),
                '{{current_time}}': datetime.now().strftime('%H:%M'),
                '{{counter}}': str(strike_info.get('counter', 0)),
                '{{anrede}}': 'Liebe' if user_info.get('gender', '').lower() in ['w', 'weiblich', 'female'] else 'Lieber'
            }

            for variable, value in variables.items():
                template = template.replace(variable, str(value))

            return template

        except Exception as e:
            self.logger.error(f"Error processing template variables: {str(e)}")
            return template

    def _send_email_to_recipients(self, message: MIMEMultipart, recipients: list) -> bool:
        try:
            if self.config.SMTP_USE_TLS:
                server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config.SMTP_SERVER, self.config.SMTP_PORT)

            server.login(self.config.EMAIL_USERNAME, self.config.EMAIL_PASSWORD)

            text = message.as_string()
            server.sendmail(self.config.EMAIL_FROM, recipients, text)

            server.quit()

            return True

        except Exception as e:
            self.logger.error(f"Error sending email to recipients {recipients}: {str(e)}")
            return False

    def send_test_email(self, recipient: Optional[str] = None) -> bool:
        try:
            test_recipient = recipient or self.config.TEST_EMAIL_RECIPIENT or self.config.EMAIL_FROM

            self.logger.info(f"Sending test email to: {test_recipient}")

            message = MIMEMultipart()
            message['Subject'] = "Lock Monitor Test Email"
            message['From'] = f"{self.config.EMAIL_FROM_NAME} <{self.config.EMAIL_FROM}>"
            message['To'] = test_recipient

            body = f"""
            <html>
            <body>
                <h2>Lock Monitor Test Email</h2>
                <p>This is a test email from the Lock Monitor Application.</p>
                <p><strong>Configuration:</strong></p>
                <ul>
                    <li>SMTP Server: {self.config.SMTP_SERVER}:{self.config.SMTP_PORT}</li>
                    <li>TLS Enabled: {self.config.SMTP_USE_TLS}</li>
                    <li>From: {self.config.EMAIL_FROM}</li>
                    <li>Test Mode: {self.config.TEST_MODE}</li>
                </ul>
                <p>If you receive this email, the email service is working correctly.</p>
                <hr>
                <small>Sent on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small>
            </body>
            </html>
            """

            html_part = MIMEText(body, 'plain', 'utf-8')
            message.attach(html_part)

            return self._send_email_to_recipients(message, [test_recipient])

        except Exception as e:
            self.logger.error(f"Error sending test email: {str(e)}")
            return False

    def test_connection(self) -> bool:
        try:
            if self.config.SMTP_USE_TLS:
                server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config.SMTP_SERVER, self.config.SMTP_PORT)

            server.login(self.config.EMAIL_USERNAME, self.config.EMAIL_PASSWORD)
            server.quit()

            self.logger.info("Email service connection test successful")
            return True

        except Exception as e:
            self.logger.error(f"Email service connection test failed: {str(e)}")
            return False
