/* ════════════════════════════════════════════════════════════
   智能营销业务系统 主 JavaScript
   Smart Marketing Business System - Main JS
   ════════════════════════════════════════════════════════════ */

// ── 全局状态 ───────────────────────────────────────────────────────────────────
const state = {
  sessionId: 'sess_' + Math.random().toString(36).substr(2, 9),
  ws: null,
  hasData: false,
  dateFrom: null,
  dateTo: null
};

// ── 工具函数 ───────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const fmt = (n, d = 2) => Number(n || 0).toLocaleString('zh-CN', {minimumFractionDigits: d, maximumFractionDigits: d});
const fmtInt = (n) => Number(n || 0).toLocaleString('zh-CN');

function toast(msg, type = 'info', duration = 3000) {
  const div = document.createElement('div');
  div.className = `toast toast-${type}`;
  div.textContent = msg;
  $('toastContainer').appendChild(div);
  setTimeout(() => div.remove(), duration);
}

function showOverlay(msg = '处理中...') {
  $('uploadOverlay').style.display = 'flex';
  $('uploadStatus').textContent = msg;
}
function hideOverlay() { $('uploadOverlay').style.display = 'none'; }

// Plotly 颜色方案
const COLORS = {
  primary: '#1890ff', success: '#52c41a', warning: '#faad14',
  danger: '#ff4d4f', purple: '#722ed1',
  sequence: ['#1890ff','#52c41a','#faad14','#ff4d4f','#722ed1',
              '#13c2c2','#eb2f96','#fa8c16','#2f54eb','#a0d911']
};
const PLOTLY_LAYOUT = {
  margin: {l: 50, r: 20, t: 30, b: 50},
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: {family: 'Microsoft YaHei, Arial, sans-serif', size: 12},
  colorway: COLORS.sequence
};

// ════════════════════════════════════════════════════════════
// 导航 Tab 切换
// ════════════════════════════════════════════════════════════
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + tab).classList.add('active');
    if (tab === 'dashboard' && state.hasData) loadDashboard();
    if (tab === 'analysis' && state.hasData) loadAnalysisTab();
    if (tab === 'reports') loadReportList();
    if (tab === 'settings') loadSettings();
  });
});

// ════════════════════════════════════════════════════════════
// 数据上传
// ════════════════════════════════════════════════════════════
const uploadZone = $('uploadZone');
const fileInput = $('fileInput');

uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
  if (e.target.files[0]) uploadFile(e.target.files[0]);
});

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

async function uploadFile(file) {
  showOverlay(`正在上传：${file.name}`);
  const formData = new FormData();
  formData.append('file', file);
  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || '上传失败');
    }
    const data = await resp.json();
    state.hasData = true;
    updateDataStatus(true, data.rows);
    hideOverlay();
    toast(`✅ 数据导入成功：${data.rows} 行记录`, 'success');
    loadDashboard();
    showUploadSummary(data);
  } catch (e) {
    hideOverlay();
    toast(`❌ 上传失败：${e.message}`, 'error', 5000);
  }
}

function showUploadSummary(data) {
  const sumDiv = document.createElement('div');
  sumDiv.className = 'sidebar-section';
  sumDiv.innerHTML = `
    <p class="sidebar-title">📄 数据摘要</p>
    <p>文件：<b>${data.filename}</b></p>
    <p>行数：<b>${fmtInt(data.rows)}</b></p>
    <p>字段：${data.columns.slice(0, 6).join('、')}${data.columns.length > 6 ? '...' : ''}</p>
  `;
  document.querySelector('.sidebar').appendChild(sumDiv);
}

function updateDataStatus(ok, rows) {
  const dot = document.querySelector('#dataStatus .dot');
  dot.className = `dot ${ok ? 'dot-green' : 'dot-gray'}`;
  $('dataStatusText').textContent = ok ? `已加载 ${fmtInt(rows)} 条` : '未上传数据';
}

// ════════════════════════════════════════════════════════════
// 日期筛选
// ════════════════════════════════════════════════════════════
function applyFilter() {
  state.dateFrom = $('dateFrom').value || null;
  state.dateTo = $('dateTo').value || null;
  loadDashboard();
  toast('筛选已应用', 'info');
}
function clearFilter() {
  state.dateFrom = null; state.dateTo = null;
  $('dateFrom').value = ''; $('dateTo').value = '';
  loadDashboard();
}

function buildQuery(base = {}) {
  const params = new URLSearchParams(base);
  if (state.dateFrom) params.set('date_from', state.dateFrom);
  if (state.dateTo) params.set('date_to', state.dateTo);
  return params;
}

// ════════════════════════════════════════════════════════════
// 仪表板加载
// ════════════════════════════════════════════════════════════
async function loadDashboard() {
  await Promise.all([loadKPI(), loadTrend(), loadProducts(), loadRegions(),
                     loadChannels(), loadForecast()]);
}

// ── KPI ───────────────────────────────────────────────────────────────────────
async function loadKPI() {
  try {
    const resp = await fetch(`/api/analysis/kpi?${buildQuery()}`);
    const kpi = await resp.json();
    renderKPI(kpi);
  } catch(e) { console.error('KPI加载失败:', e); }
}

function renderKPI(kpi) {
  const labels = {
    total_sales: '总销售额 (¥)', total_profit: '总利润 (¥)',
    avg_profit_rate: '平均利润率 (%)', order_count: '订单数',
    total_quantity: '总销量', unique_customers: '活跃客户数',
    unique_products: '产品种类', avg_order_value: '客单价 (¥)'
  };
  const row = $('kpiRow');
  row.innerHTML = Object.entries(kpi).map(([k, v]) => {
    const label = labels[k] || k;
    const val = typeof v === 'number' ? (Number.isInteger(v) ? fmtInt(v) : fmt(v)) : v;
    return `<div class="kpi-card">
      <div class="kpi-value">${val}</div>
      <div class="kpi-label">${label}</div>
    </div>`;
  }).join('');
}

// ── 趋势 ───────────────────────────────────────────────────────────────────────
async function loadTrend() {
  const freq = $('trendFreq')?.value || 'ME';
  try {
    const resp = await fetch(`/api/analysis/trend?freq=${freq}&${buildQuery()}`);
    const data = await resp.json();
    renderTrendChart(data);
  } catch(e) { console.error('趋势加载失败:', e); }
}

function renderTrendChart(data) {
  if (!data.length) { $('chartTrend').innerHTML = '<p style="padding:20px;color:#999">暂无数据</p>'; return; }
  const x = data.map(d => d.period);
  const y = data.map(d => d.sales);
  const trace = {
    x, y, type: 'scatter', mode: 'lines+markers',
    name: '销售额',
    line: {color: COLORS.primary, width: 2.5},
    marker: {size: 5},
    fill: 'tozeroy', fillcolor: 'rgba(24,144,255,.08)'
  };
  const layout = {
    ...PLOTLY_LAYOUT,
    xaxis: {title: '时间', gridcolor: '#f0f0f0'},
    yaxis: {title: '销售额 (¥)', gridcolor: '#f0f0f0', tickformat: ',.0f'}
  };
  Plotly.react('chartTrend', [trace], layout, {responsive: true, displaylogo: false});
}

// ── 产品排行 ───────────────────────────────────────────────────────────────────
async function loadProducts() {
  try {
    const resp = await fetch(`/api/analysis/products?top_n=10&${buildQuery()}`);
    const data = await resp.json();
    renderProductsChart(data.top_by_sales || []);
  } catch(e) { console.error('产品加载失败:', e); }
}

function renderProductsChart(data) {
  if (!data.length) { $('chartProducts').innerHTML = '<p style="padding:20px;color:#999">暂无数据</p>'; return; }
  const topData = data.slice(0, 10).reverse();
  const trace = {
    x: topData.map(d => d.sales),
    y: topData.map(d => (d.product || '').substring(0, 12)),
    type: 'bar', orientation: 'h',
    marker: {color: COLORS.sequence},
    text: topData.map(d => `¥${fmt(d.sales, 0)}`),
    textposition: 'outside'
  };
  Plotly.react('chartProducts', [trace],
    {...PLOTLY_LAYOUT, xaxis: {title: '销售额', gridcolor: '#f0f0f0'},
     margin: {...PLOTLY_LAYOUT.margin, l: 100}},
    {responsive: true, displaylogo: false});
}

// ── 区域 ───────────────────────────────────────────────────────────────────────
async function loadRegions() {
  try {
    const resp = await fetch(`/api/analysis/regions?${buildQuery()}`);
    const data = await resp.json();
    renderRegionsChart(data);
  } catch(e) { console.error('区域加载失败:', e); }
}

function renderRegionsChart(data) {
  if (!data.length) { $('chartRegions').innerHTML = '<p style="padding:20px;color:#999">暂无数据</p>'; return; }
  const trace = {
    values: data.map(d => d.sales),
    labels: data.map(d => d.region || '其他'),
    type: 'pie', hole: 0.38,
    textinfo: 'percent+label',
    marker: {colors: COLORS.sequence}
  };
  Plotly.react('chartRegions', [trace],
    {...PLOTLY_LAYOUT, showlegend: true,
     legend: {orientation: 'v', x: 1, y: 0.5},
     margin: {l: 20, r: 100, t: 20, b: 20}},
    {responsive: true, displaylogo: false});
}

// ── 渠道 ───────────────────────────────────────────────────────────────────────
async function loadChannels() {
  try {
    const resp = await fetch(`/api/analysis/channels?${buildQuery()}`);
    const data = await resp.json();
    renderChannelsChart(data);
  } catch(e) { console.error('渠道加载失败:', e); }
}

function renderChannelsChart(data) {
  if (!data.length) { $('chartChannels').innerHTML = '<p style="padding:20px;color:#999">暂无数据</p>'; return; }
  const trace = {
    x: data.map(d => d.channel || '其他'),
    y: data.map(d => d.sales),
    type: 'bar',
    marker: {color: COLORS.sequence},
    text: data.map(d => `¥${fmt(d.sales, 0)}`),
    textposition: 'outside'
  };
  Plotly.react('chartChannels', [trace],
    {...PLOTLY_LAYOUT, yaxis: {title: '销售额', gridcolor: '#f0f0f0'}},
    {responsive: true, displaylogo: false});
}

// ── 预测 ───────────────────────────────────────────────────────────────────────
async function loadForecast() {
  try {
    const [trendResp, forecastResp] = await Promise.all([
      fetch(`/api/analysis/trend?freq=ME&${buildQuery()}`),
      fetch('/api/analysis/forecast?periods=6&freq=ME')
    ]);
    const trendData = await trendResp.json();
    const forecastData = await forecastResp.json();
    renderForecastChart(trendData, forecastData);
  } catch(e) { console.error('预测加载失败:', e); }
}

function renderForecastChart(trend, forecast) {
  const traces = [];
  if (trend.length) {
    traces.push({
      x: trend.map(d => d.period),
      y: trend.map(d => d.sales),
      type: 'scatter', mode: 'lines+markers',
      name: '历史销售', line: {color: COLORS.primary}
    });
  }
  if (forecast.length) {
    traces.push({
      x: forecast.map(d => d.period),
      y: forecast.map(d => d.forecast_sales),
      type: 'scatter', mode: 'lines+markers',
      name: '预测', line: {color: COLORS.danger, dash: 'dash'},
      marker: {symbol: 'diamond'}
    });
  }
  if (!traces.length) { $('chartForecast').innerHTML = '<p style="padding:20px;color:#999">暂无预测数据</p>'; return; }
  Plotly.react('chartForecast', traces,
    {...PLOTLY_LAYOUT, yaxis: {title: '销售额', gridcolor: '#f0f0f0'},
     legend: {x: 0, y: 1}},
    {responsive: true, displaylogo: false});
}

// ════════════════════════════════════════════════════════════
// 分析 Tab
// ════════════════════════════════════════════════════════════
async function loadAnalysisTab() {
  await Promise.all([loadYoyMom(), loadABC(), loadAnomalies(), loadRFM()]);
}

async function runFullAnalysis() {
  toast('正在运行全量分析...', 'info');
  await loadAnalysisTab();
  toast('分析完成', 'success');
}

async function loadYoyMom() {
  try {
    const resp = await fetch('/api/analysis/yoy-mom');
    const data = await resp.json();
    renderYoyMom(data);
  } catch(e) {}
}

function renderYoyMom(d) {
  if (!d || !d.current_sales) { $('yoyContent').innerHTML = '<p style="color:#999">暂无数据</p>'; return; }
  const momPct = d.mom_pct;
  const yoyPct = d.yoy_pct;
  const momClass = momPct > 0 ? 'up' : 'down';
  const yoyClass = yoyPct > 0 ? 'up' : 'down';
  $('yoyContent').innerHTML = `
    <div class="yoy-item">
      <div class="yoy-sub">统计周期</div>
      <div class="yoy-main">${d.period || '-'}</div>
    </div>
    <div class="yoy-item">
      <div class="yoy-sub">本期销售额</div>
      <div class="yoy-main">¥${fmt(d.current_sales)}</div>
    </div>
    <div class="yoy-item">
      <div class="yoy-sub">上月 / 环比</div>
      <div class="yoy-main">¥${fmt(d.mom_sales)}</div>
      ${momPct !== null ? `<div class="yoy-pct ${momClass}">${momPct > 0 ? '▲' : '▼'} ${Math.abs(momPct)}%</div>` : ''}
    </div>
    <div class="yoy-item">
      <div class="yoy-sub">去年同期 / 同比</div>
      <div class="yoy-main">¥${fmt(d.yoy_sales)}</div>
      ${yoyPct !== null ? `<div class="yoy-pct ${yoyClass}">${yoyPct > 0 ? '▲' : '▼'} ${Math.abs(yoyPct)}%</div>` : ''}
    </div>
  `;
}

async function loadABC() {
  try {
    const resp = await fetch('/api/analysis/products?top_n=20');
    const data = await resp.json();
    renderABC(data.abc_analysis || {});
  } catch(e) {}
}

function renderABC(abc) {
  $('abcContent').innerHTML = `
    <div class="abc-card abc-a">
      <div class="abc-count">${abc.A || 0}</div>
      <div class="abc-label">A 类产品（贡献70%销售）</div>
    </div>
    <div class="abc-card abc-b">
      <div class="abc-count">${abc.B || 0}</div>
      <div class="abc-label">B 类产品（贡献20%销售）</div>
    </div>
    <div class="abc-card abc-c">
      <div class="abc-count">${abc.C || 0}</div>
      <div class="abc-label">C 类产品（贡献10%销售）</div>
    </div>
  `;
  const trace = {
    values: [abc.A || 0, abc.B || 0, abc.C || 0],
    labels: ['A类', 'B类', 'C类'],
    type: 'pie', hole: 0.4,
    marker: {colors: [COLORS.primary, COLORS.success, COLORS.warning]}
  };
  Plotly.react('chartABC', [trace],
    {...PLOTLY_LAYOUT, margin: {l:20, r:20, t:20, b:20}},
    {responsive: true, displaylogo: false});
}

async function loadAnomalies() {
  try {
    const resp = await fetch('/api/analysis/anomalies');
    const data = await resp.json();
    renderAnomalies(data);
  } catch(e) {}
}

function renderAnomalies(data) {
  if (!data.length) { $('anomalyContent').innerHTML = '<p style="color:#52c41a;padding:8px">✅ 未检测到异常数据</p>'; return; }
  $('anomalyContent').innerHTML = `<table>
    <thead><tr><th>日期</th><th>销售额</th><th>均值</th><th>偏差倍数</th></tr></thead>
    <tbody>${data.map(d => `
      <tr>
        <td>${d.date}</td>
        <td style="color:#ff4d4f">¥${fmt(d.value)}</td>
        <td>¥${fmt(d.mean)}</td>
        <td><span style="color:#ff4d4f">${d.deviation}σ</span></td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

async function loadRFM() {
  try {
    const resp = await fetch('/api/analysis/rfm');
    const data = await resp.json();
    renderRFM(data);
  } catch(e) {}
}

function renderRFM(data) {
  if (!data.length) { $('rfmContent').innerHTML = '<p style="color:#999;padding:8px">暂无客户RFM数据</p>'; return; }
  $('rfmContent').innerHTML = `<table>
    <thead><tr><th>客户</th><th>最近购买</th><th>频次</th><th>消费金额</th><th>客户等级</th></tr></thead>
    <tbody>${data.slice(0,20).map(d => `
      <tr>
        <td>${d.customer || '-'}</td>
        <td>${d.recency}天</td>
        <td>${d.frequency}次</td>
        <td>¥${fmt(d.monetary)}</td>
        <td><span style="background:#e6f7ff;color:#1890ff;padding:2px 8px;border-radius:10px;font-size:.8rem">${d.segment}</span></td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

// ════════════════════════════════════════════════════════════
// 报表
// ════════════════════════════════════════════════════════════
async function generateReport(format) {
  const title = $('reportTitle').value || '营销数据分析报告';
  showOverlay(`正在生成${format.toUpperCase()}报表...`);
  try {
    const resp = await fetch('/api/reports/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({format, title,
                             date_from: state.dateFrom,
                             date_to: state.dateTo})
    });
    const data = await resp.json();
    hideOverlay();
    if (data.status === 'success') {
      toast(`✅ 报表已生成：${data.filename}`, 'success', 5000);
      const link = document.createElement('a');
      link.href = data.download_url;
      link.download = data.filename;
      link.click();
      loadReportList();
    }
  } catch(e) {
    hideOverlay();
    toast(`❌ 报表生成失败：${e.message}`, 'error');
  }
}

async function loadReportList() {
  try {
    const resp = await fetch('/api/reports/list');
    const reports = await resp.json();
    const list = $('reportList');
    if (!reports.length) { list.innerHTML = '<p style="color:#999">暂无历史报表</p>'; return; }
    list.innerHTML = reports.map(r => `
      <div class="report-item">
        <span>${r.filename.endsWith('.xlsx') ? '📊' : '🌐'}</span>
        <span class="report-item-name">${r.filename}</span>
        <span class="report-item-meta">${new Date(r.created_at).toLocaleString('zh-CN')}</span>
        <span class="report-item-meta">${(r.size / 1024).toFixed(1)} KB</span>
        <a href="/api/reports/download/${r.filename}" download class="btn-primary btn-sm">下载</a>
      </div>
    `).join('');
  } catch(e) {}
}

async function pushSummary() {
  toast('摘要推送功能需配置微信/钉钉 Webhook', 'warn');
}

// ════════════════════════════════════════════════════════════
// 对话
// ════════════════════════════════════════════════════════════
function initWebSocket() {
  const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/chat/${state.sessionId}`;
  state.ws = new WebSocket(wsUrl);
  state.ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'typing') {
      $('typingIndicator').style.display = msg.status ? 'flex' : 'none';
    } else if (msg.type === 'message') {
      appendChatMsg(msg.content, 'assistant');
    } else if (msg.type === 'error') {
      appendChatMsg(`❌ ${msg.content}`, 'assistant');
    }
  };
  state.ws.onclose = () => {
    setTimeout(initWebSocket, 2000); // 自动重连
  };
  state.ws.onerror = () => {
    // fallback to REST
  };
}

function appendChatMsg(content, role) {
  const msgs = $('chatMessages');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  const avatar = role === 'user' ? '👤' : '🤖';
  // 渲染 Markdown
  const html = typeof marked !== 'undefined' ? marked.parse(content) : content.replace(/\n/g, '<br>');
  div.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-bubble">${html}</div>
  `;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

async function sendChatMessage() {
  const input = $('chatInput');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  appendChatMsg(msg, 'user');

  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({message: msg}));
  } else {
    // Fallback: REST API
    $('typingIndicator').style.display = 'flex';
    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: msg, session_id: state.sessionId})
      });
      const data = await resp.json();
      appendChatMsg(data.reply, 'assistant');
    } catch(e) {
      appendChatMsg('网络错误，请稍后重试', 'assistant');
    } finally {
      $('typingIndicator').style.display = 'none';
    }
  }
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
}

function sendExample(msg) {
  $('chatInput').value = msg;
  sendChatMessage();
  // 切换到对话 Tab
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="chat"]').classList.add('active');
  $('tab-chat').classList.add('active');
}

// ════════════════════════════════════════════════════════════
// 设置
// ════════════════════════════════════════════════════════════
function loadSettings() {
  const base = `${location.protocol}//${location.host}`;
  const el = $('wechatWebhook');
  if (el) el.textContent = `${base}/webhook/wechat`;
  const dd = $('dingtalkWebhook');
  if (dd) dd.textContent = `${base}/webhook/dingtalk`;
}

function saveSettings() {
  toast('配置已保存（请将配置写入 .env 文件生效）', 'success');
}

// ════════════════════════════════════════════════════════════
// 启动
// ════════════════════════════════════════════════════════════
async function init() {
  try {
    const resp = await fetch('/api/system/summary');
    const info = await resp.json();
    if (info.has_data) {
      state.hasData = true;
      updateDataStatus(true, info.data_rows);
      loadDashboard();
    }
  } catch(e) {}
  initWebSocket();
}

init();
