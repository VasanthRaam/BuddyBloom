import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

class EmailService:
    @staticmethod
    def send_otp_email(to_email: str, otp_code: str):
        if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
            print("[EMAIL SERVICE] SMTP credentials not configured. Cannot send email.")
            return False

        sender_email = settings.SMTP_EMAIL
        sender_password = settings.SMTP_PASSWORD

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your BuddyBloom Password Reset Code"
        msg["From"] = f"BuddyBloom <{sender_email}>"
        msg["To"] = to_email

        # Create the body of the message (a plain-text and an HTML version).
        text = f"Your BuddyBloom password reset code is: {otp_code}\nThis code will expire in 15 minutes."
        html = f"""\
        <html>
          <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #E2E8F0; border-radius: 12px; background-color: #F8FAFC;">
                <h2 style="color: #1E293B; text-align: center;">BuddyBloom Password Reset</h2>
                <p style="color: #475569; font-size: 16px;">Hello,</p>
                <p style="color: #475569; font-size: 16px;">We received a request to reset your password. Use the following 6-digit code to complete the process:</p>
                <div style="background-color: #2563EB; color: #ffffff; padding: 16px; border-radius: 8px; text-align: center; margin: 24px 0;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 4px;">{otp_code}</span>
                </div>
                <p style="color: #475569; font-size: 14px;">This code will expire in 15 minutes. If you did not request a password reset, please ignore this email.</p>
                <p style="color: #94A3B8; font-size: 12px; text-align: center; margin-top: 40px;">&copy; BuddyBloom Academy. All rights reserved.</p>
            </div>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")

        msg.attach(part1)
        msg.attach(part2)

        try:
            # Assuming Gmail SMTP here (smtp.gmail.com:587)
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
            server.quit()
            print(f"[EMAIL SERVICE] OTP successfully sent to {to_email}")
            return True
        except Exception as e:
            print(f"[EMAIL SERVICE] Error sending email: {e}")
            return False
