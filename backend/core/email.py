import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal

def send_email(to_email: str, subject: str, body: str):
    db = SessionLocal()
    try:
        smtp_settings = db.query(models.SmtpSettings).first()
        if not smtp_settings:
            print("ERROR: SMTP settings not found in database. Cannot send email.")
            return False

        msg = MIMEText(body, 'html') # Assuming HTML content for now
        msg['Subject'] = subject
        msg['From'] = formataddr(('Innova Tickets', smtp_settings.username))
        msg['To'] = to_email

        try:
            if smtp_settings.use_ssl:
                server = smtplib.SMTP_SSL(smtp_settings.host, smtp_settings.port)
            else:
                server = smtplib.SMTP(smtp_settings.host, smtp_settings.port)
                if smtp_settings.use_tls:
                    server.starttls()
            
            server.login(smtp_settings.username, smtp_settings.password)
            server.sendmail(smtp_settings.username, to_email, msg.as_string())
            server.quit()
            print(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            print(f"ERROR sending email to {to_email}: {e}")
            return False
    finally:
        db.close()