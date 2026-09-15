const BET_LEVELS = window.__BET_LEVELS__ || [1000, 10000, 50000, 100000, 500000, 1000000, 5000000];
let betLevelIndex = 0;

const authScreen = document.getElementById("auth-screen");
const gameScreen = document.getElementById("game-screen");
const authError = document.getElementById("auth-error");
const betError = document.getElementById("bet-error");
const betStatus = document.getElementById("bet-status");

function fmt(n) {
  return Number(n).toLocaleString("vi-VN");
}

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Lỗi không xác định");
  return data;
}

document.getElementById("btn-register").onclick = async () => {
  authError.textContent = "";
  try {
    await api("/api/register", {
      username: document.getElementById("username").value,
      password: document.getElementById("password").value,
    });
    enterGame();
  } catch (e) { authError.textContent = e.message; }
};

document.getElementById("btn-login").onclick = async () => {
  authError.textContent = "";
  try {
    await api("/api/login", {
      username: document.getElementById("username").value,
      password: document.getElementById("password").value,
    });
    enterGame();
  } catch (e) { authError.textContent = e.message; }
};

document.getElementById("btn-logout").onclick = async () => {
  await api("/api/logout");
  gameScreen.classList.add("hidden");
  authScreen.classList.remove("hidden");
};

document.getElementById("btn-inc-bet").onclick = () => {
  betLevelIndex = (betLevelIndex + 1) % BET_LEVELS.length;
  document.getElementById("bet-level").textContent = fmt(BET_LEVELS[betLevelIndex]);
};

async function placeBet(choice) {
  betError.textContent = "";
  try {
    const data = await api("/api/bet", { choice, amount: BET_LEVELS[betLevelIndex] });
    document.getElementById("balance").textContent = fmt(data.balance);
    betStatus.textContent = `Đã đặt ${choice === "tai" ? "TÀI" : "XỈU"} - ${fmt(BET_LEVELS[betLevelIndex])} đ. Chờ kết quả...`;
    document.getElementById("btn-tai").disabled = true;
    document.getElementById("btn-xiu").disabled = true;
  } catch (e) { betError.textContent = e.message; }
}
document.getElementById("btn-tai").onclick = () => placeBet("tai");
document.getElementById("btn-xiu").onclick = () => placeBet("xiu");

function renderHistory(history) {
  const body = document.getElementById("history-body");
  body.innerHTML = "";
  for (const row of history) {
    const tr = document.createElement("tr");
    const tagClass = row.result === "tai" ? "tag-tai" : row.result === "xiu" ? "tag-xiu" : "tag-bao";
    const label = row.result === "tai" ? "TÀI" : row.result === "xiu" ? "XỈU" : "BÃO";
    tr.innerHTML = `<td>${row.time}</td><td>${row.dice.join(" - ")}</td><td>${row.sum}</td><td class="${tagClass}">${label}</td>`;
    body.appendChild(tr);
  }
}

let lastRoundId = null;

async function poll() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();
    if (!data.logged_in) return;

    document.getElementById("me-username").textContent = data.username;
    document.getElementById("balance").textContent = fmt(data.balance);
    document.getElementById("countdown").textContent = data.remaining_seconds;
    renderHistory(data.history);

    if (lastRoundId && lastRoundId !== data.round_id && data.history.length) {
      const last = data.history[0];
      const tagClass = last.result === "tai" ? "tag-tai" : last.result === "xiu" ? "tag-xiu" : "tag-bao";
      const label = last.result === "tai" ? "TÀI" : last.result === "xiu" ? "XỈU" : "BÃO";
      document.getElementById("last-result").innerHTML =
        `Kết quả: ${last.dice.join(" - ")} (tổng ${last.sum}) → <span class="${tagClass}">${label}</span>`;
      document.querySelectorAll(".die").forEach((el, i) => el.textContent = last.dice[i]);
      betStatus.textContent = "";
      document.getElementById("btn-tai").disabled = false;
      document.getElementById("btn-xiu").disabled = false;
    }
    lastRoundId = data.round_id;

    if (data.my_bet) {
      document.getElementById("btn-tai").disabled = true;
      document.getElementById("btn-xiu").disabled = true;
      betStatus.textContent = `Đang cược ${data.my_bet.choice === "tai" ? "TÀI" : "XỈU"} - ${fmt(data.my_bet.amount)} đ`;
    }
  } catch (e) { /* bỏ qua lỗi mạng tạm thời */ }
}

function enterGame() {
  authScreen.classList.add("hidden");
  gameScreen.classList.remove("hidden");
  poll();
}

// Nếu đã đăng nhập từ trước (session cookie còn), tự vào game
(async function init() {
  const res = await fetch("/api/state");
  const data = await res.json();
  if (data.logged_in) enterGame();
})();

setInterval(poll, 1500);
