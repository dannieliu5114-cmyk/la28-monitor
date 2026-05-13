import requests
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────
# 监控的场次列表，可自行增减
# ─────────────────────────────────────────
SESSIONS = [
    {
        "name": "乒乓球 混双决赛",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE09?step=1",
    },
    {
        "name": "乒乓球 女单决赛",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE23?step=1",
    },
    {
        "name": "乒乓球 男单决赛",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE25?&step=1",
    },
    {
        "name": "乒乓球 混团决赛",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE37?step=1",
    },
]

SOLD_OUT_MARKER = "isShowEmptyState"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36"
}


def is_available(session: dict) -> bool:
    """返回 True 表示该场次已放票"""
    try:
        resp = requests.get(
            session["url"],
            headers=HEADERS,
            allow_redirects=True,
            timeout=15,
        )
        final_url = resp.url
        print(f"[{session['name']}] 最终落地 URL: {final_url}")
        return SOLD_OUT_MARKER not in final_url
    except Exception as e:
        print(f"[{session['name']}] 请求失败: {e}")
        return False


def send_email(available_sessions: list[dict]):
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    notify_email = os.environ["NOTIFY_EMAIL"]

    subject = "🏓 LA28 乒乓球决赛票放出来了！"

    lines = ["以下场次已可购买，请尽快前往抢购！\n"]
    for s in available_sessions:
        lines.append(f"✅ {s['name']}")
        lines.append(f"   {s['url']}\n")
    lines.append("👉 立即前往：https://hospitality.la28.org/en/event-discipline/table-tennis")

    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = notify_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, notify_email, msg.as_string())

    print(f"邮件已发送至 {notify_email}")


def main():
    available = [s for s in SESSIONS if is_available(s)]

    if available:
        print(f"发现 {len(available)} 个场次可购买，发送邮件通知...")
        send_email(available)
    else:
        print("所有场次仍为售空状态，无需通知。")


if __name__ == "__main__":
    main()
