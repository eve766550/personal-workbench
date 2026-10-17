/* ============================================================
   个人工作台 · 公共脚本
   - 统一注入导航（桌面侧边栏 + 移动底部导航）
   - 提供 localStorage 存储工具 Store
   - 提供总览台渲染 pageInit
   修改导航只需改下面的 NAV 配置，全站生效。
   ============================================================ */

const NAV = {
  sidebar: [
    { label: '总览台', href: 'index.html', key: 'index', icon: '▦' },
    { group: '每日资讯', items: [
      { label: 'AI 热点资讯', href: 'news.html', key: 'news', icon: '✦' },
      { label: '美股行情',   href: 'market.html', key: 'market', icon: '$' }
    ]},
    { label: '自媒体运营', href: 'selfmedia.html', key: 'selfmedia', icon: '✎' },
    { label: '个人成长',   href: 'growth.html', key: 'growth', icon: '✚' },
    { label: '个人计划',   href: 'plan.html', key: 'plan', icon: '◷' }
  ],
  bottom: [
    { label: '总览', href: 'index.html', key: 'index', icon: '▦' },
    { label: '资讯', href: 'news.html', key: 'news', icon: '✦' },
    { label: '自媒体', href: 'selfmedia.html', key: 'selfmedia', icon: '✎' },
    { label: '成长', href: 'growth.html', key: 'growth', icon: '✚' },
    { label: '计划', href: 'plan.html', key: 'plan', icon: '◷' }
  ]
};

/* ---------- 存储工具 ---------- */
const Store = {
  get(k, def) {
    try { const v = localStorage.getItem('wb.' + k); return v ? JSON.parse(v) : def; }
    catch (e) { return def; }
  },
  set(k, v) { localStorage.setItem('wb.' + k, JSON.stringify(v)); },
  add(k, item) {
    const arr = this.get(k, []);
    item.id = item.id || (Date.now() + '' + Math.floor(Math.random() * 1000));
    arr.unshift(item);
    this.set(k, arr);
    return item;
  },
  remove(k, id) {
    const arr = this.get(k, []);
    this.set(k, arr.filter(x => String(x.id) !== String(id)));
  },
  update(k, id, patch) {
    const arr = this.get(k, []);
    this.set(k, arr.map(x => String(x.id) === String(id) ? { ...x, ...patch } : x));
  }
};

/* ---------- 日期工具 ---------- */
function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function cnDate() {
  const d = new Date();
  const w = ['周日','周一','周二','周三','周四','周五','周六'][d.getDay()];
  return (d.getMonth() + 1) + ' 月 ' + d.getDate() + ' 日 · ' + w;
}
function calcStreak(dates) {
  if (!dates || !dates.length) return 0;
  const set = new Set(dates);
  let streak = 0;
  const d = new Date();
  for (let i = 0; ; i++) {
    const day = new Date(d);
    day.setDate(d.getDate() - i);
    const key = day.getFullYear() + '-' + String(day.getMonth() + 1).padStart(2, '0') + '-' + String(day.getDate()).padStart(2, '0');
    if (set.has(key)) streak++;
    else if (i === 0) continue;   // 今天还没打卡不算断
    else break;
  }
  return streak;
}

/* ---------- 导航注入 ---------- */
function injectNav() {
  const page = document.body.dataset.page ||
    location.pathname.split('/').pop().replace('.html', '').replace('', '') || 'index';

  const sb = document.getElementById('sidebar');
  if (sb) {
    let html = '<div class="brand"><span class="dot"></span>个人工作台</div><nav class="nav">';
    NAV.sidebar.forEach(item => {
      if (item.group) {
        html += '<div class="nav-group-title">' + item.group + '</div>';
        item.items.forEach(it => html += navItem(it, page));
      } else {
        html += navItem(item, page);
      }
    });
    html += '</nav>';
    sb.innerHTML = html;
  }

  const bn = document.getElementById('bottomNav');
  if (bn) {
    bn.innerHTML = NAV.bottom.map(it => {
      const active = it.key === page ? ' active' : '';
      return '<a class="bn-item' + active + '" href="' + it.href + '">' +
             '<span class="bn-icon">' + it.icon + '</span><span>' + it.label + '</span></a>';
    }).join('');
  }
}
function navItem(it, page) {
  const active = it.key === page ? ' active' : '';
  return '<a class="nav-item' + active + '" href="' + it.href + '">' +
         '<span class="nav-icon">' + it.icon + '</span><span>' + it.label + '</span></a>';
}

/* ---------- 总览台渲染 ---------- */
function renderIndex() {
  // 今日焦点：AI 头条
  const newsData = window.AI_NEWS || {};
  const news = newsData.items || [];
  const fn = document.getElementById('focus-news');
  if (fn) {
    fn.innerHTML = news.length
      ? '<a class="focus-link" href="news.html">' + news[0].title +
        '<span class="muted"> · ' + news[0].source + '</span></a>'
      : '<span class="muted">今日资讯更新中…</span>';
  }
  const hintNews = document.getElementById('hint-news');
  if (hintNews && newsData.updatedAt) {
    hintNews.textContent = '来自 AI 资讯 · 更新 ' + newsData.updatedAt;
  }

  // 今日焦点：三大指数
  const mkt = window.US_MARKET || { indices: [] };
  const fm = document.getElementById('focus-market');
  if (fm) {
    let html = (mkt.indices || []).slice(0, 3).map(ix => {
      const up = ix.change >= 0;
      const sign = up ? '+' : '';
      return '<div class="mini-index"><span>' + ix.name + '</span><b class="' +
             (up ? 'up' : 'down') + '">' + sign + ix.changePct.toFixed(2) + '%</b></div>';
    }).join('');
    if (!html) {
      html = '<span class="muted">行情更新中…</span>';
    } else if (mkt.date) {
      html += '<div class="data-meta">数据日期 ' + mkt.date + '（美东收盘）· 更新 ' +
              (mkt.updatedAt || '—') + '</div>';
    }
    fm.innerHTML = html;
  }
  const hintMarket = document.getElementById('hint-market');
  if (hintMarket) {
    hintMarket.textContent = mkt.date ? mkt.date + ' 收盘 · 红涨绿跌' : '红涨绿跌';
  }

  // 数字卡片
  const todos = Store.get('todos', []);
  const ideas = Store.get('ideas', []);
  const learning = Store.get('learning', []);
  const checkin = Store.get('checkin', { dates: [] });
  const done = todos.filter(t => t.done).length;
  const streak = calcStreak(checkin.dates);

  setText('stat-done', done);
  setText('stat-ideas', ideas.length);
  setText('stat-learning', learning.filter(x => x.progress < 100).length);
  setText('stat-streak', streak);

  // 本周小结
  const weekly = document.getElementById('weekly');
  if (weekly) {
    weekly.innerHTML =
      '<div class="mini-index"><span>本周完成待办</span><b>' + done + ' 项</b></div>' +
      '<div class="mini-index"><span>连续打卡</span><b>' + streak + ' 天</b></div>' +
      '<div class="mini-index"><span>灵感收集</span><b>' + ideas.length + ' 条</b></div>' +
      '<div class="mini-index"><span>进行中学习</span><b>' + learning.filter(x => x.progress < 100).length + ' 项</b></div>';
  }

  renderTodos();
}

function renderTodos() {
  const list = document.getElementById('todo-list');
  if (!list) return;
  const todos = Store.get('todos', []);
  if (!todos.length) {
    list.innerHTML = '<li class="empty">今天还没有待办，下面加一条吧</li>';
    return;
  }
  list.innerHTML = todos.map(t =>
    '<li class="' + (t.done ? 'done' : '') + '">' +
      '<label><input type="checkbox" data-id="' + t.id + '" ' + (t.done ? 'checked' : '') + '>' +
      '<span>' + escapeHtml(t.text) + '</span></label>' +
      '<button class="del" data-id="' + t.id + '" title="删除">×</button></li>'
  ).join('');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

/* ---------- 各页初始化入口 ---------- */
const PAGE_INIT = {
  index: renderIndex
  // news / market / selfmedia / growth / plan 在第 2、3 阶段实现
};

document.addEventListener('DOMContentLoaded', function () {
  injectNav();
  const page = document.body.dataset.page ||
    location.pathname.split('/').pop().replace('.html', '') || 'index';
  if (typeof PAGE_INIT[page] === 'function') PAGE_INIT[page]();

  // 总览台待办交互（事件委托）
  if (page === 'index') {
    const addBtn = document.getElementById('todo-add-btn');
    const input = document.getElementById('todo-input');
    if (addBtn && input) {
      addBtn.addEventListener('click', () => {
        const text = input.value.trim();
        if (!text) return;
        Store.add('todos', { text, done: false, date: todayStr() });
        input.value = '';
        renderTodos();
        renderIndex();
      });
      input.addEventListener('keydown', e => { if (e.key === 'Enter') addBtn.click(); });
    }
    const list = document.getElementById('todo-list');
    if (list) {
      list.addEventListener('change', e => {
        if (e.target.matches('input[type=checkbox]')) {
          Store.update('todos', e.target.dataset.id, { done: e.target.checked });
          renderTodos();
          renderIndex();
        }
      });
      list.addEventListener('click', e => {
        if (e.target.classList.contains('del')) {
          Store.remove('todos', e.target.dataset.id);
          renderTodos();
          renderIndex();
        }
      });
    }
  }
});
