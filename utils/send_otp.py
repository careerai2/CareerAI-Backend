import smtplib
from email.mime.text import MIMEText
import random
import os


async def send_otp_email(receiver_email: str, otp: int) -> int:
    """Send OTP to the given email and return the generated OTP."""

    # Generate 6-digit OTP
    # otp = random.randint(100000, 999999)

    # Sender credentials
    sender_email = os.getenv("SENDER_EMAIL", "your_email@gmail.com")
    password = os.getenv("SENDER_PASSWORD", "your_app_password")  # Use Gmail App Password

    # Email Content
    subject = "Your OTP Code"
    body = f"Your OTP for signup is {otp}. It is valid for 5 minutes."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    # Send Email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print(f"OTP {otp} sent to {receiver_email}")
        return otp
    except Exception as e:
        print(f"Error sending OTP: {e}")
        raise ValueError("Failed to send OTP email")
        return -1
