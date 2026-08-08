import os
import re
import json
import smtplib
import requests
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 "
             "Mobile/15E148 Safari/604.1")
PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


# ---------- 状态读写（用文件保存，配合 Actions 缓存） ----------
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


# ---------- 各平台检测 ----------
def check_huya(room):
    resp = requests.get(f"https://m.huya.com/{room}",
                        headers={"User-Agent": MOBILE_UA}, timeout=10)
    text = resp.text
    m = re.search(r'"eLiveStatus"\s*:\s*(\d+)', text)
    if m:
        return int(m.group(1)) == 2          # 2=直播中 3=回放 0/1=未开播
    m2 = re.search(r'ISLIVE\s*=\s*(true|false)', text, re.IGNORECASE)
    if m2:
        return m2.group(1).lower() == "true"
    return ("直播中" in text and "回放" not in text) or None


def check_bili(room):
    resp = requests.get(
        f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room}",
        headers={"User-Agent": PC_UA, "Referer": "https://live.bilibili.com/"},
        timeout=10)
    data = resp.json()
    if data.get("code") == 0:
        return data["data"].get("live_status") == 1
    return None


def check_douyin(room):
    resp = requests.get(f"https://live.douyin.com/{room}",
                        headers={"User-Agent": PC_UA,
                                 "Referer": "https://live.douyin.com/"},
                        timeout=10)
    m = re.search(r'"status"\s*:\s*(\d+)', resp.text)
    if m:
        return m.group(1) == "2"
    return None


def check(s):
    p = s.get("platform", "").lower()
    try:
        if p == "huya":
            return check_huya(s["room_id"])
        if p in ("bilibili", "bili"):
            return check_bili(s["room_id"])
        if p in ("douyin", "dy"):
            return check_douyin(s["room_id"])
    except Exception as e:
        print(f"[check error] {s.get('name')}: {e}")
    return None


# ---------- 完全免费的通知 ----------
def send_qq_email(subject, body):
    """QQ邮箱SMTP → 微信「QQ邮箱提醒」插件，完全免费不限量"""
    sender = os.environ.get("QQ_EMAIL_SENDER", "")
    auth = os.environ.get("QQ_EMAIL_AUTH", "")
    receiver = os.environ.get("QQ_EMAIL_RECEIVER", "") or sender
    if not sender or not auth:
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15) as s:
            s.login(sender, auth)
            s.sendmail(sender, [receiver], msg.as_string())
        print("✅ 邮件发送成功，微信「QQ邮箱提醒」会弹出通知")
        return True
    except Exception as e:
        print(f"❌ 邮件失败: {e}")
        return False


def send_wxpusher(title, content):
    """WxPusher 备用通道（也是免费）"""
    token = os.environ.get("WXPUSHER_APP_TOKEN", "")
    uid = os.environ.get("WXPUSHER_UID", "")
    if not token or not uid:
        return False
    try:
        r = requests.post("https://wxpusher.zjiecode.com/api/send/message", json={
            "appToken": token, "uids": [uid], "summary": title,
            "content": f"<h3>{title}</h3><p>{content}</p>", "contentType": 2,
        }, timeout=10)
        print("WxPusher:", r.status_code)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ WxPusher 失败: {e}")
        return False


def notify(title, content):
    if send_qq_email(title, content):
        return
    send_wxpusher(title, content)   # 邮件没配/失败时走备用


# ---------- 主流程 ----------
def main():
    # 手动点 Run workflow 时，先发一条测试通知验证链路
    if os.environ.get("TEST") == "1":
        notify("✅ 测试通知", "GitHub Actions 主播监控已部署成功，通知链路正常。")

    streamers = json.loads(os.environ.get("STREAMERS", "[]"))
    if not streamers:
        print("未配置 STREAMERS")
        return

    state = load_state()
    newly = []

    for s in streamers:
        key = f"{s.get('platform')}:{s.get('room_id')}"
        old = state.get(key)
        cur = check(s)
        print(f"{s.get('name')} -> {cur}")
        if cur is None:
            continue
        if cur is True and old is False:   # 未开播 → 直播中，才算新开播
            newly.append(s)
        state[key] = cur

    save_state(state)

    if newly:
        title = (f"🔴 {newly[0]['name']} 开播啦！" if len(newly) == 1
                 else f"🔴 {len(newly)} 位主播上线啦！")
        base = {"huya": "https://www.huya.com/",
                "bilibili": "https://live.bilibili.com/",
                "douyin": "https://live.douyin.com/"}
        lines = [f"【{s['platform']}】{s['name']}\n{base.get(s['platform'], '')}{s['room_id']}"
                 for s in newly]
        notify(title, "\n\n".join(lines))


if __name__ == "__main__":
    main()
