"""
Game Tài Xỉu - Demo dùng TIỀN ẢO trong game (không phải tiền thật).
Chạy: python app.py
Mở trình duyệt: http://127.0.0.1:5000
"""
import json
import os
import random
import threading
import time
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, session, render_template

app = Flask(__name__)
app.secret_key = "doi-key-nay-truoc-khi-deploy-that"  # đổi trước khi deploy thật

ROUND_SECONDS = 60          # mỗi 1 phút tung xúc xắc 1 lần
STARTING_BALANCE = 50_000   # cấp sẵn 50k khi tạo tài khoản
BET_LEVELS = [1_000, 10_000, 50_000, 100_000, 500_000, 1_000_000, 5_000_000]
WIN_MULTIPLIER = 0.98       # thắng ăn 98% số tiền cược
HISTORY_LIMIT = 50

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

lock = threading.Lock()

# ---- Lưu trữ: users + history được load/ghi ra file JSON (data.json) ----
users = {}          # username -> {"password": str, "balance": int}
pending_bets = {}    # username -> {"choice": "tai"/"xiu", "amount": int}  (không lưu file, mất khi restart là hợp lý)
history = []         # list of {"dice":[..], "sum":int, "result":str, "time":str}


def load_data():
    """Đọc users + history từ data.json nếu file đã tồn tại."""
    global users, history
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            users = saved.get("users", {})
            history = saved.get("history", [])
        except (json.JSONDecodeError, OSError):
            # File hỏng/rỗng -> bỏ qua, bắt đầu với dữ liệu trống
            users = {}
            history = []


def save_data():
    """Ghi users + history hiện tại ra data.json. Gọi hàm này bên trong 'with lock'."""
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump({"users": users, "history": history}, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, DATA_FILE)  # ghi đè an toàn, tránh hỏng file nếu mất điện giữa chừng


load_data()

game_state = {
    "round_id": str(uuid.uuid4()),
    "next_roll_at": time.time() + ROUND_SECONDS,
}


def compute_result(dice):
    total = sum(dice)
    if dice[0] == dice[1] == dice[2]:
        return "bao"  # bộ ba giống nhau -> nhà cái thắng cả hai bên (luật phổ biến)
    return "tai" if total >= 11 else "xiu"


def settle_round():
    """Tung xúc xắc, xử lý toàn bộ cược đang chờ, lưu lịch sử."""
    with lock:
        dice = [random.randint(1, 6) for _ in range(3)]
        result = compute_result(dice)

        for username, bet in pending_bets.items():
            user = users.get(username)
            if not user:
                continue
            amount = bet["amount"]
            choice = bet["choice"]
            # Lưu ý: số tiền cược đã bị trừ ngay lúc đặt cược (xem /api/bet).
            # Thắng: hoàn lại vốn + 98% lợi nhuận (tổng nhận về = 1.98 x tiền cược).
            # Thua: không hoàn lại gì (đã mất 100% số tiền cược).
            if result != "bao" and choice == result:
                user["balance"] += int(amount * (1 + WIN_MULTIPLIER))

        history.insert(0, {
            "dice": dice,
            "sum": sum(dice),
            "result": result,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        del history[HISTORY_LIMIT:]

        pending_bets.clear()
        game_state["round_id"] = str(uuid.uuid4())
        game_state["next_roll_at"] = time.time() + ROUND_SECONDS
        save_data()


def game_loop():
    while True:
        remaining = game_state["next_roll_at"] - time.time()
        if remaining > 0:
            time.sleep(min(remaining, 1))
        else:
            settle_round()


threading.Thread(target=game_loop, daemon=True).start()


# ---------------- Routes ----------------

@app.route("/")
def index():
    return render_template("index.html", bet_levels=BET_LEVELS)


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "Thiếu tên đăng nhập hoặc mật khẩu"}), 400
    with lock:
        if username in users:
            return jsonify({"error": "Tài khoản đã tồn tại"}), 400
        users[username] = {"password": password, "balance": STARTING_BALANCE}
        save_data()
    session["username"] = username
    return jsonify({"ok": True, "balance": STARTING_BALANCE})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = users.get(username)
    if not user or user["password"] != password:
        return jsonify({"error": "Sai tên đăng nhập hoặc mật khẩu"}), 400
    session["username"] = username
    return jsonify({"ok": True, "balance": user["balance"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    return jsonify({"ok": True})


def current_user():
    username = session.get("username")
    if not username or username not in users:
        return None
    return username


@app.route("/api/bet", methods=["POST"])
def place_bet():
    username = current_user()
    if not username:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    data = request.get_json(force=True)
    choice = data.get("choice")
    amount = data.get("amount")

    if choice not in ("tai", "xiu"):
        return jsonify({"error": "Chọn Tài hoặc Xỉu"}), 400
    if amount not in BET_LEVELS:
        return jsonify({"error": "Mức cược không hợp lệ"}), 400

    with lock:
        if username in pending_bets:
            return jsonify({"error": "Bạn đã đặt cược cho ván này rồi"}), 400
        user = users[username]
        if user["balance"] < amount:
            return jsonify({"error": "Số dư không đủ"}), 400
        user["balance"] -= amount  # trừ tiền ngay khi đặt; nếu thắng sẽ cộng lại ở settle_round
        pending_bets[username] = {"choice": choice, "amount": amount}
        save_data()

    return jsonify({"ok": True, "balance": user["balance"]})


@app.route("/api/state")
def state():
    username = current_user()
    with lock:
        my_bet = pending_bets.get(username) if username else None
        balance = users[username]["balance"] if username else None
        remaining = max(0, int(game_state["next_roll_at"] - time.time()))
        return jsonify({
            "logged_in": username is not None,
            "username": username,
            "balance": balance,
            "remaining_seconds": remaining,
            "round_id": game_state["round_id"],
            "my_bet": my_bet,
            "history": history,
            "bet_levels": BET_LEVELS,
        })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
