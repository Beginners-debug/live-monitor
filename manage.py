import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "streamers.json")

ALIASES = {"huya": "huya", "bili": "bilibili", "bilibili": "bilibili",
           "douyin": "douyin", "dy": "douyin"}

def load():
    if os.path.exists(FILE):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save(lst):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)

def main():
    mode = os.environ.get("MODE", "").strip()
    p = os.environ.get("PLATFORM", "").strip().lower()
    platform = ALIASES.get(p, p)
    room = os.environ.get("ROOM_ID", "").strip()
    name = os.environ.get("NAME", "").strip() or room

    if mode == "add":
        if platform not in ("huya", "bilibili", "douyin") or not room:
            print("⚠️ 添加需要正确的 platform 和 room_id")
            return
        lst = load()
        if any(s.get("platform") == platform and str(s.get("room_id")) == room for s in lst):
            print("该主播已存在，不重复添加")
            return
        lst.append({"platform": platform, "room_id": room, "name": name})
        save(lst)
        print(f"✅ 已添加: [{platform}] {name} ({room})")

    elif mode == "delete":
        if not room:
            print("⚠️ 删除需要填 room_id")
            return
        lst = load()
        before = len(lst)
        lst = [s for s in lst if not (str(s.get("room_id")) == room
               and (platform == "" or s.get("platform") == platform))]
        save(lst)
        print(f"✅ 已删除 {before - len(lst)} 个主播")

    elif mode == "list":
        lst = load()
        if not lst:
            print("(列表为空)")
        for s in lst:
            print(f"- [{s.get('platform')}] {s.get('name')} (房间号: {s.get('room_id')})")

if __name__ == "__main__":
    main()
