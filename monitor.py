import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

SESSIONS = [
    {"name": "乒乓球 混双决赛", "code": "TTE09", "url": "https://hospitality.la28.org/en/products/TTE/TTE09?step=1"},
    {"name": "乒乓球 女单决赛", "code": "TTE23", "url": "https://hospitality.la28.org/en/products/TTE/TTE23?step=1"},
    {"name": "乒乓球 男单决赛", "code": "TTE25", "url": "https://hospitality.la28.org/en/products/TTE/TTE25?step=1"},
    {"name": "乒乓球 混团决赛", "code": "TTE37", "url": "https://hospitality.la28.org/en/products/TTE/TTE37?step=1"},
]

LIST_URL = "https://hospitality.la28.org/en/products?events=TTE&dates=&groupSize=1"

# 售空信号（任一出现即为售空）
SOLD_OUT_MARKERS = [
    "register interest",        # 详情页有 Register Interest 按钮
    "sold out",                 # 详情页显示 "Looks like those packages are sold out"
]

LIST_AVAILABLE_MARKER = "select"

WAITING_ROOM_MARKERS = [
    "you are now in line",
    "it is your turn",
    "you will have 10 minutes",
    "period of high demand",
    "thank you for waiting",
]


def is_waiting_room(content: str) -> bool:
    return any(m in content for m in WAITING_ROOM_MARKERS)


def is_sold_out_content(content: str) -> bool:
    return any(m in content for m in SOLD_OUT_MARKERS)


def load_all_sessions(page):
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


def check_list_page(session: dict, page) -> tuple[bool, bool]:
    """
    主要检测：列表页
    - 场次有 Select 按钮 → (True, True)
    - 场次未出现 / 有售空标志 → (False, True)
    - 等候室 / 报错 → (False, False)
    """
    try:
        page.goto(LIST_URL, wait_until="networkidle", timeout=60000)
        content = page.inner_text("body").lower()

        if is_waiting_room(content):
            print(f"  [列表页] 进入等候室，不可靠")
            return False, False

        load_all_sessions(page)
        content = page.inner_text("body").lower()

        if session["code"].lower() not in content:
            print(f"  [列表页] 场次 {session['code']} 未出现（已隐藏或售空）")
            return False, True

        cards = page.locator(f"text={session['code']}").all()
        for card in cards:
            try:
                parent_text = card.locator("xpath=ancestor::*[5]").inner_text().lower()
                if LIST_AVAILABLE_MARKER in parent_text and not is_sold_out_content(parent_text):
                    print(f"  [列表页] 场次 {session['code']} 有 Select 按钮 → 有票！")
                    return True, True
            except Exception:
                continue

        print(f"  [列表页] 场次 {session['code']} 存在但无 Select 按钮 → 售空")
        return False, True

    except Exception as e:
        print(f"  [列表页] 请求失败: {e}")
        return False, False


def check_detail_page(session: dict, page) -> tuple[bool, bool]:
    """
    备用检测：详情页（仅在列表页不可靠时使用）
    售空状态1：显示 "Register Interest" 按钮
    售空状态2：显示 "Looks like those packages are sold out"
    两种都能识别
    """
    try:
        page.goto(session["url"], wait_until="networkidle", timeout=60000)
        content = page.inner_text("body").lower()

        if is_waiting_room(content):
            print(f"  [详情页] 进入等候室，不可靠")
            return False, False

        sold_out = is_sold_out_content(content)
        print(f"  [详情页] 售空标志存在: {sold_out}")
        return not sold_out, True

    except Exception as e:
        print(f"  [详情页] 请求失败: {e}")
        return False, False


def is_available(session: dict, page) -> bool:
    print(f"\n[{session['name']}] 开始检测...")

    list_avail, list_reliable = check_list_page(session, page)

    if list_reliable:
        print(f"  → 列表页可靠，最终判断: {'有票！' if list_avail else '售空'}")
        return list_avail

    print(f"  列表页不可靠，回退到详情页...")
    detail_avail, detail_reliable = check_detail_page(session, page)

    if detail_reliable:
        print(f"  → 详情页兜底，最终判断: {'有票！' if detail_avail else '售空'}")
        return detail_avail

    print(f"  → 两个检测均不可靠，本次跳过")
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
