(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  /* ---------- Toast ---------- */
  const toastEl = $("#toast");
  let toastTimer;
  function toast(text, color) {
    toastEl.textContent = text;
    toastEl.style.borderColor = color || "var(--border)";
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
  }

  /* ---------- Reveal on scroll ---------- */
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    });
  }, { threshold: 0.15 });
  $$(".reveal").forEach((el, i) => {
    el.style.transitionDelay = `${(i % 4) * 0.08}s`;
    io.observe(el);
  });

  /* ---------- Hero network canvas ---------- */
  const canvas = $("#net");
  const ctx = canvas.getContext("2d");
  let nodes = [], W, H;
  function resize() {
    const dpr = window.devicePixelRatio || 1;
    W = canvas.offsetWidth; H = canvas.offsetHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.min(70, Math.floor((W * H) / 18000));
    nodes = Array.from({ length: count }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 2 + 1,
    }));
  }
  const mouse = { x: -999, y: -999 };
  canvas.parentElement.addEventListener("mousemove", (e) => {
    const r = canvas.getBoundingClientRect();
    mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
  });
  canvas.parentElement.addEventListener("mouseleave", () => { mouse.x = mouse.y = -999; });
  function draw() {
    ctx.clearRect(0, 0, W, H);
    for (const n of nodes) {
      n.x += n.vx; n.y += n.vy;
      if (n.x < 0 || n.x > W) n.vx *= -1;
      if (n.y < 0 || n.y > H) n.vy *= -1;
    }
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < 140) {
          ctx.strokeStyle = `rgba(108,99,255,${1 - d / 140})`;
          ctx.lineWidth = 0.7;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
      const n = nodes[i];
      const md = Math.hypot(n.x - mouse.x, n.y - mouse.y);
      if (md < 180) {
        ctx.strokeStyle = `rgba(52,211,153,${1 - md / 180})`;
        ctx.beginPath(); ctx.moveTo(n.x, n.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
      }
      ctx.fillStyle = md < 180 ? "#34d399" : "#a78bfa";
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill();
    }
    if (!reduceMotion) requestAnimationFrame(draw);
  }
  resize(); draw();
  window.addEventListener("resize", resize);

  /* ---------- Hero IP typing ---------- */
  const heroIp = $("#heroIp");
  const ips = ["192.168.1.25", "10.0.0.50", "172.16.5.12", "192.168.0.100", "DHCP (otomatik)"];
  let ipIdx = 0;
  async function typeLoop() {
    if (reduceMotion) return;
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    while (true) {
      await sleep(2200);
      const cur = heroIp.textContent;
      for (let i = cur.length; i >= 0; i--) { heroIp.textContent = cur.slice(0, i); await sleep(35); }
      ipIdx = (ipIdx + 1) % ips.length;
      const next = ips[ipIdx];
      for (let i = 1; i <= next.length; i++) { heroIp.textContent = next.slice(0, i); await sleep(75); }
    }
  }
  typeLoop();

  /* ---------- Ripple on buttons ---------- */
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".abtn, .btn");
    if (!b || reduceMotion) return;
    const r = b.getBoundingClientRect();
    const s = Math.max(r.width, r.height);
    const span = document.createElement("span");
    span.className = "ripple";
    span.style.cssText = `width:${s}px;height:${s}px;left:${e.clientX - r.left - s / 2}px;top:${e.clientY - r.top - s / 2}px`;
    b.appendChild(span);
    setTimeout(() => span.remove(), 600);
  });

  /* ---------- Confetti ---------- */
  function confetti() {
    if (reduceMotion) return;
    const colors = ["#6c63ff", "#34d399", "#fbbf24", "#22d3ee", "#f87171", "#a78bfa"];
    for (let i = 0; i < 70; i++) {
      const c = document.createElement("span");
      c.className = "confetti";
      c.style.left = Math.random() * 100 + "vw";
      c.style.background = colors[i % colors.length];
      c.style.animationDuration = 1.6 + Math.random() * 1.8 + "s";
      c.style.animationDelay = Math.random() * 0.3 + "s";
      document.body.appendChild(c);
      setTimeout(() => c.remove(), 4000);
    }
  }

  /* ---------- App simulation ---------- */
  const app = $("#app");
  const fields = {};
  $$(".oct").forEach((box) => {
    const inputs = [];
    for (let i = 0; i < 4; i++) {
      const inp = document.createElement("input");
      inp.inputMode = "numeric"; inp.maxLength = 3;
      inp.setAttribute("aria-label", `${box.dataset.f} ${i + 1}. kutu`);
      inp.addEventListener("input", () => {
        inp.value = inp.value.replace(/\D/g, "");
        if (+inp.value > 255) inp.value = "255";
        if (inp.value.length === 3 && inputs[i + 1]) inputs[i + 1].focus();
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "." && inputs[i + 1]) { e.preventDefault(); inputs[i + 1].focus(); }
        if (e.key === "Backspace" && !inp.value && inputs[i - 1]) inputs[i - 1].focus();
      });
      inputs.push(inp);
      box.appendChild(inp);
      if (i < 3) { const dot = document.createElement("i"); dot.textContent = "."; box.appendChild(dot); }
    }
    fields[box.dataset.f] = inputs;
  });
  const getF = (f) => fields[f].map((i) => i.value).join(".");
  const isFull = (f) => fields[f].every((i) => i.value !== "");
  async function setF(f, value, animate = true) {
    const parts = value ? value.split(".") : ["", "", "", ""];
    for (let i = 0; i < 4; i++) {
      fields[f][i].value = parts[i] ?? "";
      if (animate && !reduceMotion) {
        fields[f][i].classList.remove("typed"); void fields[f][i].offsetWidth;
        fields[f][i].classList.add("typed");
        await new Promise((r) => setTimeout(r, 60));
      }
    }
  }
  setF("mask", "255.255.255.0", false);
  setF("dns", "8.8.8.8", false);

  const msg = $("#msg");
  let msgTimer;
  function showMsg(text, color) {
    msg.textContent = text; msg.style.color = color;
    clearTimeout(msgTimer);
    msgTimer = setTimeout(() => (msg.textContent = ""), 4000);
  }

  const curIp = $("#curIp"), curMode = $("#curMode");
  function setCurrent(ip, mode) {
    curIp.textContent = ip;
    curIp.classList.remove("flash"); void curIp.offsetWidth; curIp.classList.add("flash");
    curMode.textContent = mode === "static" ? "STATİK" : "DHCP";
    curMode.className = "mode " + mode;
  }

  $("#adapter").addEventListener("change", (e) => {
    $("#ifaceName").textContent = e.target.value;
    setCurrent(e.target.value === "Wi-Fi" ? "192.168.1.31" : "192.168.1.25", "dhcp");
  });

  function shake() {
    app.classList.remove("shake"); void app.offsetWidth; app.classList.add("shake");
  }

  const applyBtn = $("#applyBtn"), dhcpBtn = $("#dhcpBtn");
  function busy(on) { applyBtn.disabled = dhcpBtn.disabled = on; }

  applyBtn.addEventListener("click", () => {
    if (!isFull("ip") || !isFull("mask") || !isFull("gw")) {
      showMsg("IP, Subnet, and Gateway are required!", "var(--danger)");
      toast("❌ IP, Subnet ve Gateway kutularını doldurmalısın", "var(--danger)");
      shake();
      return;
    }
    busy(true);
    showMsg("Applying...", "var(--warning)");
    setTimeout(() => {
      busy(false);
      setCurrent(getF("ip"), "static");
      showMsg("Applied successfully", "var(--success)");
      toast(`✅ Artık adresin: ${getF("ip")}`, "var(--success)");
      confetti();
    }, 1200);
  });

  dhcpBtn.addEventListener("click", () => {
    busy(true);
    showMsg("Switching to DHCP...", "var(--warning)");
    setTimeout(() => {
      busy(false);
      const ip = `192.168.1.${100 + Math.floor(Math.random() * 120)}`;
      setCurrent(ip, "dhcp");
      showMsg("Switched to DHCP", "var(--success)");
      toast(`📮 Modem sana otomatik adres verdi: ${ip}`, "var(--success)");
    }, 1000);
  });

  /* Profiles */
  let profiles = [
    { name: "Ofis", ip: "10.0.0.50", gateway: "10.0.0.1" },
    { name: "Ev", ip: "192.168.1.50", gateway: "192.168.1.1" },
  ];
  const list = $("#profiles");
  function renderProfiles() {
    list.innerHTML = "";
    profiles.forEach((p, idx) => {
      const el = document.createElement("div");
      el.className = "prof";
      el.style.animationDelay = `${idx * 0.06}s`;
      el.innerHTML = `<b></b><small></small>
        <div class="prof-btns"><button class="pload">Load</button><button class="pdel" aria-label="Sil">x</button></div>`;
      el.querySelector("b").textContent = p.name;
      el.querySelector("small").textContent = p.ip;
      el.querySelector(".pload").onclick = async () => {
        await setF("ip", p.ip);
        await setF("gw", p.gateway);
        showMsg(`Loaded '${p.name}'`, "var(--success)");
      };
      el.querySelector(".pdel").onclick = () => {
        el.classList.add("out");
        setTimeout(() => {
          profiles.splice(profiles.indexOf(p), 1);
          renderProfiles();
          toast(`🗑️ '${p.name}' silindi`);
        }, 330);
      };
      list.appendChild(el);
    });
    $("#profCount").textContent = profiles.length;
  }
  renderProfiles();

  $("#saveBtn").addEventListener("click", () => {
    if (!isFull("ip")) {
      showMsg("Enter an IP address first.", "var(--danger)");
      toast("Önce IP kutularını doldur ✍️", "var(--danger)");
      shake();
      return;
    }
    const name = prompt("Profile name:", "Yeni profil");
    if (!name || !name.trim()) return;
    profiles.push({ name: name.trim(), ip: getF("ip"), gateway: isFull("gw") ? getF("gw") : "" });
    renderProfiles();
    showMsg(`Saved '${name.trim()}'`, "var(--success)");
  });

  /* Subtle 3D tilt on the app window */
  if (!reduceMotion && window.matchMedia("(pointer: fine)").matches) {
    app.addEventListener("mousemove", (e) => {
      const r = app.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      app.style.transform = `perspective(1400px) rotateY(${x * 4}deg) rotateX(${-y * 4}deg)`;
    });
    app.addEventListener("mouseleave", () => { app.style.transform = ""; });
  }

  /* ---------- Copy buttons ---------- */
  $$(".copy").forEach((b) => {
    b.addEventListener("click", async () => {
      const text = b.previousElementSibling.textContent;
      try { await navigator.clipboard.writeText(text); } catch {
        const ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); } catch {}
        ta.remove();
      }
      b.textContent = "Kopyalandı ✓"; b.classList.add("ok");
      setTimeout(() => { b.textContent = "Kopyala"; b.classList.remove("ok"); }, 1600);
    });
  });

  /* ---------- Tabs ---------- */
  $$(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      $$(".tab").forEach((x) => x.classList.toggle("active", x === t));
      $$(".panel").forEach((p) => p.classList.toggle("active", p.id === t.dataset.tab));
    });
  });
})();
