import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────
# 监控的决赛场次
# ─────────────────────────────────────────
SESSIONS = [
    {
        "name": "乒乓球 混双决赛",
        "code": "TTE09",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE09?step=1",
    },
    {
        "name": "乒乓球 女单决赛",
        "code": "TTE23",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE23?step=1",
    },
    {
        "name": "乒乓球 男单决赛",
        "code": "TTE25",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE25?step=1",
    },
    {
        "name": "乒乓球 混团决赛",
        "code": "TTE37",
        "url": "https://hospitality.la28.org/en/products/TTE/TTE37?step=1",
    },
]

LIST_URL = "https://hospitality.la28.org/en/products?events=TTE&dates=&groupSize=1"
SOLD_OUT_MARKER = "register interest"
LIST_AVAILABLE_MARKER = "select"


def load_all_sessions(page):
    """持续点击 Show More 直到所有场次加载完毕"""
    while True:
        try:
            show_more = page.locator("text=Show More").first
            if show_more.is_visible(timeout=3000):
                show_more.click()
                page.wait_for_load_state("networkidle", timeout=15000)
            else:
                break
        except Exception:
            break


def check_detail_page(session: dict, page) -> bool:
    """详情页：页面上完全没有 'register interest' → 有票"""
    try:
        page.goto(session["url"], wait_until="networkidle", timeout=60000)
        content = page.inner_text("body").lower()
        sold_out = SOLD_OUT_MARKER in content
        print(f"  [详情页] 售空标志存在: {sold_out}")
        return not sold_out
    except Exception as e:
        print(f"  [详情页] 请求失败: {e}")
        return False


def check_list_page(session: dict, page) -> bool:
    """
    列表页：点击所有 Show More 加载全部场次，
    找到对应场次代码且按钮为 Select（非 Register Interest）即为有票。
    场次未出现视为售空。
    """
    try:
        page.goto(LIST_URL, wait_until="networkidle", timeout=60000)

        # 展开所有场次
        load_all_sessions(page)

        content = page.inner_text("body").lower()

        # 场次未出现 → 售空/隐藏
        if session["code"].lower() not in content:
            print(f"  [列表页] 场次 {session['code']} 未出现（已隐藏或售空）")
            return False

        # 找到场次卡片，检查按钮
        cards = page.locator(f"text={session['code']}").all()
        for card in cards:
            try:
                parent_text = card.locator("xpath=ancestor::*[5]").inner_text().lower()
                if LIST_AVAILABLE_MARKER in parent_text and SOLD_OUT_MARKER not in parent_text:
                    print(f"  [列表页] 场次 {session['code']} 有 Select 按钮 → 有票")
                    return True
            except Exception:
                continue

        print(f"  [列表页] 场次 {session['code']} 存在但无 Select 按钮 → 售空")
        return False
    except Exception as e:
        print(f"  [列表页] 请求失败: {e}")
        return False


def is_available(session: dict, page) -> bool:
    """详情页或列表页任一检测到有票即通知（OR 逻辑）"""
    print(f"\n[{session['name']}] 开始检测...")
    detail = check_detail_page(session, page)
    listing = check_list_page(session, page)
    result = detail or listing
    print(f"  → 最终判断: {'有票！' if result else '售空'}")
    return result


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

    print(f"\n邮件已发送至 {notify_email}")


def main():
    available = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for session in SESSIONS:
            if is_available(session, page):
                available.append(session)
        browser.close()

    if available:
        print(f"\n发现 {len(available)} 个场次可购买，发送邮件通知...")
        send_email(available)
    else:
        print("\n所有场次仍为售空状态，无需通知。")


if __name__ == "__main__":
    main()
