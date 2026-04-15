// PineScript Backtester - Frontend Application

const API = '';
let currentBacktestId = null;
let pollInterval = null;
let equityChart = null;
let drawdownChart = null;
let currentReport = null;
let dataSource = 'yahoo';
let csvFile = null;
let currentTheme = 'light';

// -- Theme --------------------------------------------------------------------

function setTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('rc-theme', theme);
    document.getElementById('theme-light').classList.toggle('active', theme === 'light');
    document.getElementById('theme-dark').classList.toggle('active', theme === 'dark');
    // Re-render charts if they exist (to update grid/text colors)
    if (currentReport) {
        renderEquityChart(currentReport.equity_curve);
        renderDrawdownChart(currentReport.equity_curve);
    }
}

function getChartColors() {
    const style = getComputedStyle(document.documentElement);
    return {
        grid: style.getPropertyValue('--chart-grid').trim(),
        text: style.getPropertyValue('--chart-text').trim(),
        accent: style.getPropertyValue('--accent').trim(),
        red: style.getPropertyValue('--red').trim(),
    };
}

// -- Navigation ---------------------------------------------------------------

function showView(name) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-' + name).classList.add('active');
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    const idx = { input: 0, history: 1 }[name];
    if (idx !== undefined && document.querySelectorAll('nav button')[idx]) {
        document.querySelectorAll('nav button')[idx].classList.add('active');
    }
    if (name === 'history') loadHistory();
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
}

// -- Data Source Toggle -------------------------------------------------------

function setDataSource(source) {
    dataSource = source;
    document.querySelectorAll('.data-source-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('ds-' + source).classList.add('active');
    document.getElementById('csv-upload-section').style.display = source === 'csv' ? 'block' : 'none';
    document.getElementById('mt5-export-section').style.display = source === 'mt5' ? 'block' : 'none';
    updateRunButtonLabel();
}

function updateRunButtonLabel() {
    const btn = document.getElementById('run-btn');
    if (!btn) return;
    btn.textContent = dataSource === 'mt5' ? 'Direct Run' : 'Run Backtest';
}

function getBacktestConfig() {
    return {
        pinescript: document.getElementById('pinescript-code').value.trim(),
        symbol: document.getElementById('symbol').value.trim() || 'XAUUSD',
        timeframe: document.getElementById('timeframe').value,
        start_date: document.getElementById('start-date').value,
        end_date: document.getElementById('end-date').value,
        initial_capital: parseFloat(document.getElementById('initial-capital').value) || 10000,
        leverage: parseFloat(document.getElementById('leverage').value) || 1,
        commission_pct: parseFloat(document.getElementById('commission').value) || 0,
        slippage_points: parseFloat(document.getElementById('slippage').value) || 0,
        input_overrides: getInputOverrides(),
    };
}

function onCsvFileSelected(event) {
    csvFile = event.target.files[0];
    if (csvFile) {
        document.getElementById('csv-file-label').innerHTML =
            '<span class="file-selected">' + csvFile.name + '</span> (' + (csvFile.size / 1024).toFixed(1) + ' KB)';
    }
}

// Drag & drop support
document.addEventListener('DOMContentLoaded', () => {
    updateRunButtonLabel();
    const dropZone = document.getElementById('csv-drop-zone');
    if (!dropZone) return;
    ['dragenter', 'dragover'].forEach(ev => {
        dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    });
    ['dragleave', 'drop'].forEach(ev => {
        dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove('dragover'); });
    });
    dropZone.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        if (files.length > 0 && (files[0].name.endsWith('.csv') || files[0].name.endsWith('.txt'))) {
            csvFile = files[0];
            document.getElementById('csv-file-label').innerHTML =
                '<span class="file-selected">' + csvFile.name + '</span> (' + (csvFile.size / 1024).toFixed(1) + ' KB)';
        }
    });
});

// -- MT5 DataExporter Script Generator ----------------------------------------

function generateMT5Script() {
    const symbol = document.getElementById('symbol').value.trim() || 'XAUUSD';
    const tf = document.getElementById('timeframe').value;
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value || new Date().toISOString().slice(0, 10);

    // Map timeframe to MQL5 ENUM_TIMEFRAMES
    const tfMap = {
        '1m': 'PERIOD_M1', '5m': 'PERIOD_M5', '15m': 'PERIOD_M15',
        '30m': 'PERIOD_M30', '1h': 'PERIOD_H1', '4h': 'PERIOD_H4',
        '1d': 'PERIOD_D1', '1wk': 'PERIOD_W1'
    };
    const mql5TF = tfMap[tf] || 'PERIOD_D1';

    // Format dates for MQL5 datetime: D'YYYY.MM.DD'
    const fmtDate = (d) => "D'" + d.replace(/-/g, '.') + "'";

    const script = `//+------------------------------------------------------------------+
//| Auto-generated DataExporter for ${symbol} ${tf}
//| Generated by Rey Capital PineScript Backtester
//|
//| Usage: Drag this script onto any chart in MetaTrader 5.
//| The CSV will be saved to: MQL5/Files/${symbol}_${tf}_data.csv
//+------------------------------------------------------------------+
#property copyright "Rey Capital"
#property version   "1.00"
#property script_show_inputs

input string          InpSymbol    = "${symbol}";
input ENUM_TIMEFRAMES InpTimeframe = ${mql5TF};
input datetime        InpStartDate = ${fmtDate(startDate)};
input datetime        InpEndDate   = ${fmtDate(endDate)};
input string          InpFileName  = "${symbol}_${tf}_data.csv";

string TimeframeToString(ENUM_TIMEFRAMES tf) {
   switch(tf) {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      case PERIOD_W1:  return "W1";
      case PERIOD_MN1: return "MN1";
      default:         return "UNK";
   }
}

void OnStart() {
   string symbol = InpSymbol;
   if(symbol == "" || symbol == NULL) symbol = Symbol();

   if(!SymbolSelect(symbol, true)) {
      PrintFormat("Error: Symbol '%s' not found.", symbol);
      return;
   }

   ENUM_TIMEFRAMES timeframe = InpTimeframe;
   if(timeframe == PERIOD_CURRENT) timeframe = Period();

   datetime startDate = InpStartDate;
   datetime endDate   = InpEndDate;
   if(endDate == 0) endDate = TimeCurrent();

   string fileName = InpFileName;
   if(fileName == "" || fileName == NULL)
      fileName = symbol + "_" + TimeframeToString(timeframe) + "_data.csv";

   PrintFormat("=== Rey Capital Data Exporter ===");
   PrintFormat("Symbol: %s | TF: %s | %s to %s",
               symbol, TimeframeToString(timeframe),
               TimeToString(startDate, TIME_DATE),
               TimeToString(endDate, TIME_DATE));

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(symbol, timeframe, startDate, endDate, rates);

   if(copied <= 0) {
      PrintFormat("Error: CopyRates failed (%d). Error=%d", copied, GetLastError());
      return;
   }

   PrintFormat("Retrieved %d bars. Writing CSV...", copied);

   int fh = FileOpen(fileName, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(fh == INVALID_HANDLE) {
      PrintFormat("Error: Cannot open file. Error=%d", GetLastError());
      return;
   }

   FileWrite(fh, "Date", "Time", "Open", "High", "Low", "Close", "Volume");

   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   int step = MathMax(copied / 10, 1);

   for(int i = 0; i < copied; i++) {
      FileWrite(fh,
         TimeToString(rates[i].time, TIME_DATE),
         TimeToString(rates[i].time, TIME_MINUTES),
         DoubleToString(rates[i].open, digits),
         DoubleToString(rates[i].high, digits),
         DoubleToString(rates[i].low, digits),
         DoubleToString(rates[i].close, digits),
         IntegerToString(rates[i].tick_volume));

      if((i+1) % step == 0 || i == copied-1)
         PrintFormat("Progress: %d/%d (%.0f%%)", i+1, copied, (double)(i+1)/copied*100);
   }

   FileClose(fh);
   PrintFormat("=== Done: %d bars -> %s ===", copied, fileName);
}
`;

    const container = document.getElementById('mt5-script-output');
    container.innerHTML = `
        <div class="mql5-script-preview">
            <div class="script-header">
                <span>DataExporter_${symbol}_${tf}.mq5</span>
                <button class="btn btn-primary btn-sm" onclick="downloadMT5Script()">Download .mq5 File</button>
            </div>
            <pre>${escapeHtml(script)}</pre>
        </div>
        <p style="font-size:0.78rem;color:var(--text-muted);margin-top:8px;">
            Save this file to your MT5 <b>MQL5/Scripts/</b> folder, compile it, then drag it onto a chart.
            The exported CSV will appear in <b>MQL5/Files/</b>. Upload it using the "Upload CSV File" data source option.
        </p>
    `;

    // Store for download
    container._scriptContent = script;
    container._scriptName = `DataExporter_${symbol}_${tf}.mq5`;
}

function downloadMT5Script() {
    const container = document.getElementById('mt5-script-output');
    if (!container._scriptContent) return;
    const blob = new Blob([container._scriptContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = container._scriptName;
    a.click();
    URL.revokeObjectURL(url);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// -- Parse PineScript ---------------------------------------------------------

async function parseCode() {
    const code = document.getElementById('pinescript-code').value.trim();
    if (!code) return;

    try {
        const res = await fetch(API + '/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });
        const data = await res.json();
        showParseResult(data);
    } catch (e) {
        console.error('Parse error:', e);
    }
}

function showParseResult(data) {
    const container = document.getElementById('parse-result');
    const warnings = document.getElementById('parse-warnings');
    const params = document.getElementById('parse-params');

    container.style.display = 'block';

    let warnHtml = '';
    if (data.errors && data.errors.length) {
        warnHtml += data.errors.map(e => `<div class="warning">${e}</div>`).join('');
    }
    if (data.warnings && data.warnings.length) {
        warnHtml += data.warnings.map(w => `<div class="warning" style="border-color: var(--text-muted); color: var(--text-muted);">${w}</div>`).join('');
    }
    if (data.strategy_name) {
        warnHtml = `<p style="margin-bottom:8px;color:var(--green);">Strategy: <b>${data.strategy_name}</b></p>` + warnHtml;
    }
    if (data.indicators_found && data.indicators_found.length) {
        warnHtml += `<p style="margin:8px 0;font-size:0.82rem;color:var(--text-secondary);">Indicators: ${data.indicators_found.join(', ')}</p>`;
    }
    warnings.innerHTML = warnHtml;

    const inputs = data.inputs || [];
    params.innerHTML = inputs.map(inp => `
        <div class="param-item">
            <span class="param-name">${inp.title || inp.name}</span>
            <input type="${inp.type === 'bool' ? 'checkbox' : inp.type === 'string' ? 'text' : 'number'}"
                   data-param="${inp.name}"
                   ${inp.type === 'bool' ? (inp.default ? 'checked' : '') : `value="${inp.default}"`}
                   ${inp.min_val != null ? `min="${inp.min_val}"` : ''}
                   ${inp.max_val != null ? `max="${inp.max_val}"` : ''}
                   ${inp.step != null ? `step="${inp.step}"` : ''}>
        </div>
    `).join('');
}

function getInputOverrides() {
    const overrides = {};
    document.querySelectorAll('#parse-params input[data-param]').forEach(el => {
        const name = el.dataset.param;
        if (el.type === 'checkbox') overrides[name] = el.checked;
        else if (el.type === 'number') overrides[name] = parseFloat(el.value);
        else overrides[name] = el.value;
    });
    return overrides;
}

// -- Run Backtest -------------------------------------------------------------

async function runBacktest() {
    const config = getBacktestConfig();
    const code = config.pinescript;
    if (!code) { alert('Please enter PineScript strategy code.'); return; }

    if (dataSource === 'csv' && !csvFile) {
        alert('Please select a CSV file for historical data.');
        return;
    }

    const btn = document.getElementById('run-btn');
    btn.disabled = true;

    try {
        let btId;

        if (dataSource === 'csv') {
            const formData = new FormData();
            formData.append('file', csvFile);
            formData.append('pinescript', code);
            formData.append('symbol', document.getElementById('symbol').value.trim() || 'CUSTOM');
            formData.append('timeframe', config.timeframe);
            formData.append('initial_capital', String(config.initial_capital));
            formData.append('leverage', String(config.leverage));
            formData.append('commission_pct', String(config.commission_pct));
            formData.append('slippage_points', String(config.slippage_points));
            formData.append('input_overrides', JSON.stringify(getInputOverrides()));

            const res = await fetch(API + '/api/backtest/csv', { method: 'POST', body: formData });
            const data = await res.json();
            if (!res.ok) { alert(data.detail || 'CSV upload failed'); return; }
            btId = data.id;
            currentBacktestId = btId;
        } else if (dataSource === 'mt5') {
            const res = await fetch(API + '/api/backtest/mt5', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const data = await res.json();
            if (!res.ok) { alert(data.detail || 'MT5 backtest submission failed'); return; }
            btId = data.id;
            currentBacktestId = btId;
        } else {
            const res = await fetch(API + '/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const data = await res.json();
            if (!res.ok) { alert(data.detail || 'Backtest submission failed'); return; }
            btId = data.id;
            currentBacktestId = btId;

            if (data.warning) {
                document.getElementById('data-warning').style.display = 'block';
                document.getElementById('data-warning').textContent = data.warning;
            }
        }

        showView('progress');
        startPolling(btId);
    } catch (e) {
        alert('Error submitting backtest: ' + e.message);
    } finally {
        btn.disabled = false;
    }
}

// -- Polling ------------------------------------------------------------------

function startPolling(btId) {
    if (pollInterval) clearInterval(pollInterval);
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Initializing...';
    document.getElementById('progress-title').textContent = 'Running Backtest...';
    const spinnerEl = document.querySelector('.spinner');
    if (spinnerEl) spinnerEl.style.display = 'inline-block';
    pollInterval = setInterval(() => pollStatus(btId), 1000);
}

async function pollStatus(btId) {
    try {
        const res = await fetch(API + `/api/backtest/${btId}/status`);
        const data = await res.json();

        document.getElementById('progress-bar').style.width = data.progress + '%';
        document.getElementById('progress-text').textContent = data.phase || data.status;

        if (data.status === 'complete') {
            clearInterval(pollInterval);
            pollInterval = null;
            await loadReport(btId);
        } else if (data.status === 'error') {
            clearInterval(pollInterval);
            pollInterval = null;
            document.getElementById('progress-title').textContent = 'Backtest Failed';
            document.getElementById('progress-text').textContent = data.error || 'Unknown error';
            document.querySelector('.spinner').style.display = 'none';
        }
    } catch (e) {
        console.error('Poll error:', e);
    }
}

// -- Report -------------------------------------------------------------------

async function loadReport(btId) {
    try {
        const res = await fetch(API + `/api/backtest/${btId}/report`);
        currentReport = await res.json();
        renderReport(currentReport);
        showView('report');
    } catch (e) {
        alert('Error loading report: ' + e.message);
    }
}

function renderReport(report) {
    renderSettings(report);
    renderMetrics(report.metrics);
    renderEquityChart(report.equity_curve);
    renderDrawdownChart(report.equity_curve);
    renderOrdersTable(report.orders);
    renderDealsTable(report.deals);
    renderSummary(report.summary);
}

function renderSettings(report) {
    const el = document.getElementById('report-settings');
    const downloadedCandles = report?.metrics?.bars ?? '-';
    const inputs = (report.inputs || []).map(i =>
        `<span class="label">${i.title || i.name}:</span><span class="value">${i.default}</span>`
    ).join('');
    el.innerHTML = `
        <h2>Strategy Tester Report</h2>
        <div class="settings-grid">
            <span class="label">Strategy:</span><span class="value">${report.strategy_name || report.name}</span>
            <span class="label">Symbol:</span><span class="value">${report.symbol}</span>
            <span class="label">Period:</span><span class="value">${report.period}</span>
            <span class="label">Initial Capital:</span><span class="value">${fmt(report.initial_capital)}</span>
            <span class="label">Leverage:</span><span class="value">1:${report.leverage}</span>
            <span class="label">Commission:</span><span class="value">${report.commission_pct}%</span>
            <span class="label">Downloaded Candles:</span><span class="value">${downloadedCandles}</span>
            ${inputs}
        </div>
    `;
}

function renderMetrics(m) {
    const el = document.getElementById('report-metrics');
    el.innerHTML = `
    <div class="metrics-grid">
        <div class="metrics-column">
            <div class="metrics-section-title">Performance</div>
            ${metricRow('Total Net Profit', fmt(m.total_net_profit), m.total_net_profit)}
            ${metricRow('Gross Profit', fmt(m.gross_profit), m.gross_profit)}
            ${metricRow('Gross Loss', fmt(m.gross_loss), m.gross_loss)}
            ${metricRow('Profit Factor', m.profit_factor?.toFixed(2))}
            ${metricRow('Recovery Factor', m.recovery_factor?.toFixed(2))}
            ${metricRow('Expected Payoff', m.expected_payoff?.toFixed(2))}
            ${metricRow('Sharpe Ratio', m.sharpe_ratio?.toFixed(2))}
            ${metricRow('AHPR', `${m.ahpr?.toFixed(4)} (${m.ahpr_pct?.toFixed(2)}%)`)}
            ${metricRow('GHPR', `${m.ghpr?.toFixed(4)} (${m.ghpr_pct?.toFixed(2)}%)`)}
            <div class="metrics-section-title">Other</div>
            ${metricRow('Bars', m.bars)}
            ${metricRow('Total Deals', m.total_deals)}
            ${metricRow('LR Correlation', m.lr_correlation?.toFixed(6))}
            ${metricRow('LR Standard Error', m.lr_standard_error?.toFixed(2))}
        </div>
        <div class="metrics-column">
            <div class="metrics-section-title">Drawdown</div>
            ${metricRow('Balance DD Absolute', fmt(m.balance_dd_absolute), -m.balance_dd_absolute)}
            ${metricRow('Balance DD Maximal', `${fmt(m.balance_dd_maximal)} (${m.balance_dd_maximal_pct?.toFixed(2)}%)`, -m.balance_dd_maximal)}
            ${metricRow('Balance DD Relative', `${m.balance_dd_relative_pct?.toFixed(2)}% (${fmt(m.balance_dd_relative_val)})`, -m.balance_dd_relative_pct)}
            ${metricRow('Equity DD Absolute', fmt(m.equity_dd_absolute), -m.equity_dd_absolute)}
            ${metricRow('Equity DD Maximal', `${fmt(m.equity_dd_maximal)} (${m.equity_dd_maximal_pct?.toFixed(2)}%)`, -m.equity_dd_maximal)}
            ${metricRow('Equity DD Relative', `${m.equity_dd_relative_pct?.toFixed(2)}% (${fmt(m.equity_dd_relative_val)})`, -m.equity_dd_relative_pct)}
            <div class="metrics-section-title">Consecutive</div>
            ${metricRow('Max Consec. Wins ($)', `${m.max_consecutive_wins} (${fmt(m.max_consecutive_wins_money)})`)}
            ${metricRow('Max Consec. Losses ($)', `${m.max_consecutive_losses} (${fmt(m.max_consecutive_losses_money)})`)}
            ${metricRow('Max Consec. Profit (count)', `${fmt(m.max_consecutive_profit)} (${m.max_consecutive_profit_count})`)}
            ${metricRow('Max Consec. Loss (count)', `${fmt(m.max_consecutive_loss)} (${m.max_consecutive_loss_count})`)}
            ${metricRow('Avg Consec. Wins', m.avg_consecutive_wins)}
            ${metricRow('Avg Consec. Losses', m.avg_consecutive_losses)}
        </div>
        <div class="metrics-column">
            <div class="metrics-section-title">Trades</div>
            ${metricRow('Total Trades', m.total_trades)}
            ${metricRow('Short Trades (won %)', `${m.short_trades} (${m.short_trades_won_pct?.toFixed(2)}%)`)}
            ${metricRow('Long Trades (won %)', `${m.long_trades} (${m.long_trades_won_pct?.toFixed(2)}%)`)}
            ${metricRow('Profit Trades (% of total)', `${m.profit_trades} (${m.profit_trades_pct?.toFixed(2)}%)`)}
            ${metricRow('Loss Trades (% of total)', `${m.loss_trades} (${m.loss_trades_pct?.toFixed(2)}%)`)}
            ${metricRow('Largest Profit Trade', fmt(m.largest_profit_trade), m.largest_profit_trade)}
            ${metricRow('Largest Loss Trade', fmt(m.largest_loss_trade), m.largest_loss_trade)}
            ${metricRow('Average Profit Trade', fmt(m.average_profit_trade), m.average_profit_trade)}
            ${metricRow('Average Loss Trade', fmt(m.average_loss_trade), m.average_loss_trade)}
            <div class="metrics-section-title">Correlation & Timing</div>
            ${metricRow('Corr (Profits, MFE)', m.corr_profits_mfe?.toFixed(4))}
            ${metricRow('Corr (Profits, MAE)', m.corr_profits_mae?.toFixed(4))}
            ${metricRow('Corr (MFE, MAE)', m.corr_mfe_mae?.toFixed(4))}
            ${metricRow('Min Holding Time', m.min_holding_time || '-')}
            ${metricRow('Max Holding Time', m.max_holding_time || '-')}
            ${metricRow('Avg Holding Time', m.avg_holding_time || '-')}
            ${metricRow('Z-Score', `${m.z_score?.toFixed(2)} (${m.z_score_pct?.toFixed(2)}%)`)}
        </div>
    </div>`;
}

function metricRow(label, value, colorVal) {
    let cls = 'metric-value';
    if (colorVal !== undefined) {
        if (colorVal > 0) cls += ' positive';
        else if (colorVal < 0) cls += ' negative';
    }
    return `<div class="metric-row"><span class="metric-label">${label}</span><span class="${cls}">${value ?? '-'}</span></div>`;
}

function renderEquityChart(curve) {
    if (equityChart) equityChart.destroy();
    if (!curve || !curve.length) return;

    const cc = getChartColors();
    const ctx = document.getElementById('equity-chart').getContext('2d');
    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: curve.map(p => p.timestamp ? p.timestamp.slice(0, 10) : ''),
            datasets: [{
                label: 'Balance',
                data: curve.map(p => p.balance),
                borderColor: cc.accent,
                backgroundColor: cc.accent + '14',
                fill: true,
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.1,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxTicksLimit: 12, color: cc.text, font: { size: 10 } }, grid: { color: cc.grid } },
                y: { ticks: { color: cc.text, font: { size: 10 } }, grid: { color: cc.grid } }
            }
        }
    });
}

function renderDrawdownChart(curve) {
    if (drawdownChart) drawdownChart.destroy();
    if (!curve || !curve.length) return;

    const cc = getChartColors();
    const ctx = document.getElementById('drawdown-chart').getContext('2d');
    drawdownChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: curve.map(p => p.timestamp ? p.timestamp.slice(0, 10) : ''),
            datasets: [{
                label: 'Drawdown %',
                data: curve.map(p => -(p.drawdown_pct || 0)),
                borderColor: cc.red,
                backgroundColor: cc.red + '18',
                fill: true,
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.1,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxTicksLimit: 12, color: cc.text, font: { size: 10 } }, grid: { color: cc.grid } },
                y: { ticks: { color: cc.text, font: { size: 10 }, callback: v => v.toFixed(1) + '%' }, grid: { color: cc.grid } }
            }
        }
    });
}

function renderOrdersTable(orders) {
    const tbody = document.querySelector('#orders-table tbody');
    if (!orders || !orders.length) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted);">No orders</td></tr>';
        return;
    }
    tbody.innerHTML = orders.map(o => `
        <tr>
            <td>${o.open_time || ''}</td><td>${o.order_num || ''}</td><td>${o.symbol || ''}</td>
            <td class="${o.type}">${o.type || ''}</td><td>${o.volume || ''}</td><td>${fmtPrice(o.price)}</td>
            <td>${o.sl ? fmtPrice(o.sl) : ''}</td><td>${o.tp ? fmtPrice(o.tp) : ''}</td>
            <td>${o.state || ''}</td><td>${o.comment || ''}</td>
        </tr>
    `).join('');
}

function renderDealsTable(deals) {
    const tbody = document.querySelector('#deals-table tbody');
    if (!deals || !deals.length) {
        tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;color:var(--text-muted);">No deals</td></tr>';
        return;
    }
    tbody.innerHTML = deals.map(d => `
        <tr>
            <td>${d.time || ''}</td><td>${d.deal_num || ''}</td><td>${d.symbol || ''}</td>
            <td class="${d.type}">${d.type || ''}</td><td>${d.direction || ''}</td><td>${d.volume || ''}</td>
            <td>${fmtPrice(d.price)}</td><td>${d.order_num || ''}</td>
            <td>${d.commission ? d.commission.toFixed(2) : '0'}</td><td>${d.swap ? d.swap.toFixed(2) : '0'}</td>
            <td class="${d.profit > 0 ? 'positive' : d.profit < 0 ? 'negative' : ''}">${d.profit ? d.profit.toFixed(2) : '0'}</td>
            <td>${d.balance ? d.balance.toFixed(2) : ''}</td><td>${d.comment || ''}</td>
        </tr>
    `).join('');
}

function renderSummary(summary) {
    if (!summary) return;
    const el = document.getElementById('report-summary');
    el.innerHTML = `
        <h2>Summary</h2>
        <table><tr class="summary-row">
            <td>Total Commission</td><td class="${summary.total_commission < 0 ? 'negative' : ''}">${fmt(summary.total_commission)}</td>
            <td>Total Swap</td><td>${fmt(summary.total_swap)}</td>
            <td>Total Profit</td><td class="${summary.total_profit >= 0 ? 'positive' : 'negative'}">${fmt(summary.total_profit)}</td>
            <td>Final Balance</td><td><b>${fmt(summary.final_balance)}</b></td>
        </tr></table>
    `;
}

// -- History ------------------------------------------------------------------

async function loadHistory() {
    try {
        const res = await fetch(API + '/api/backtests');
        const data = await res.json();
        renderHistory(data);
    } catch (e) { console.error('History error:', e); }
}

function renderHistory(items) {
    const el = document.getElementById('history-list');
    if (!items || !items.length) {
        el.innerHTML = '<div class="empty-state">No backtests yet. Run your first backtest!</div>';
        return;
    }
    el.innerHTML = items.map(item => `
        <div class="history-item" onclick="${item.status === 'complete' ? `loadReport(${item.id})` : ''}">
            <div class="info">
                <div class="name">${item.name} ${item.strategy_name ? '- ' + item.strategy_name : ''}</div>
                <div class="detail">${item.symbol} | ${item.period} | ${item.created_at?.slice(0, 19) || ''}</div>
            </div>
            <div class="stats">
                ${item.status === 'complete' ? `
                    <div><div class="stat-label">Net Profit</div><span class="${item.total_net_profit >= 0 ? 'positive' : 'negative'}">${fmt(item.total_net_profit)}</span></div>
                    <div><div class="stat-label">Profit Factor</div>${item.profit_factor?.toFixed(2) || '-'}</div>
                    <div><div class="stat-label">Trades</div>${item.total_trades}</div>
                    <div><div class="stat-label">Win Rate</div>${item.win_rate?.toFixed(1) || 0}%</div>
                    <div><div class="stat-label">Max DD</div>${item.max_drawdown_pct?.toFixed(1) || 0}%</div>
                ` : `<span style="color:var(--${item.status === 'error' ? 'red' : 'yellow'})">${item.status}</span>`}
            </div>
            ${item.status === 'complete' ? `<button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteBacktest(${item.id})">Del</button>` : ''}
        </div>
    `).join('');
}

async function deleteBacktest(id) {
    if (!confirm('Delete this backtest?')) return;
    try {
        await fetch(API + `/api/backtest/${id}`, { method: 'DELETE' });
        loadHistory();
    } catch (e) { console.error('Delete error:', e); }
}

// -- CSV Download -------------------------------------------------------------

function downloadCSV() {
    if (!currentReport || !currentReport.deals) return;
    const headers = ['Time','Deal','Symbol','Type','Direction','Volume','Price','Order','Commission','Swap','Profit','Balance','Comment'];
    const rows = currentReport.deals.map(d =>
        [d.time, d.deal_num, d.symbol, d.type, d.direction, d.volume, d.price, d.order_num, d.commission, d.swap, d.profit, d.balance, d.comment].join(',')
    );
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `backtest_${currentReport.symbol}_deals.csv`; a.click();
    URL.revokeObjectURL(url);
}

// -- HTML Report Download -----------------------------------------------------

function downloadHTML() {
    if (!currentReport) return;
    const r = currentReport;
    const m = r.metrics || {};
    const isDark = currentTheme === 'dark';
    const bg = isDark ? '#0a0e1a' : '#f0f2f5';
    const bgCard = isDark ? '#1a2340' : '#e8ecf1';
    const bgSec = isDark ? '#111827' : '#ffffff';
    const text = isDark ? '#e8eaf0' : '#1a1a2e';
    const textMuted = isDark ? '#5c6478' : '#8892a4';
    const accent = isDark ? '#3b82f6' : '#1B4FBE';
    const border = isDark ? '#1e293b' : '#d8dee6';
    const green = isDark ? '#22c55e' : '#16a34a';
    const red = isDark ? '#ef4444' : '#dc2626';

    const metricsHTML = buildMetricsHTML(m, accent, bgCard, border, text, textMuted, green, red);
    const ordersHTML = buildOrdersHTML(r.orders || [], accent, bgCard, border, text);
    const dealsHTML = buildDealsHTML(r.deals || [], accent, bgCard, border, text, green, red);
    const summaryHTML = r.summary ? `
        <table style="width:100%;border-collapse:collapse;font-size:0.78rem"><tr style="background:${bgCard};font-weight:600">
            <td style="padding:10px;border-top:2px solid ${accent}">Total Commission</td><td style="padding:10px;border-top:2px solid ${accent}">${fmt(r.summary.total_commission)}</td>
            <td style="padding:10px;border-top:2px solid ${accent}">Total Swap</td><td style="padding:10px;border-top:2px solid ${accent}">${fmt(r.summary.total_swap)}</td>
            <td style="padding:10px;border-top:2px solid ${accent}">Total Profit</td><td style="padding:10px;border-top:2px solid ${accent};color:${r.summary.total_profit>=0?green:red}">${fmt(r.summary.total_profit)}</td>
            <td style="padding:10px;border-top:2px solid ${accent}">Final Balance</td><td style="padding:10px;border-top:2px solid ${accent}"><b>${fmt(r.summary.final_balance)}</b></td>
        </tr></table>` : '';

    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Backtest Report - ${r.symbol}</title>
<style>body{font-family:Arial,sans-serif;background:${bg};color:${text};padding:24px;max-width:1400px;margin:0 auto}
h1{color:${accent};font-size:1.3rem;border-bottom:2px solid ${border};padding-bottom:10px}h2{color:${accent};font-size:1rem;margin-top:24px}
.settings{display:grid;grid-template-columns:130px 1fr;gap:4px 14px;font-size:0.85rem;margin-bottom:18px}.settings .lbl{color:${textMuted}}.settings .val{color:${text}}
.brand{display:flex;align-items:center;gap:10px;margin-bottom:16px}.brand-name{font-size:14px;font-weight:800;letter-spacing:1.5px;color:${accent}}.brand-sub{font-size:11px;color:${textMuted}}
</style></head><body>
<div class="brand"><svg width="28" height="28" viewBox="0 0 100 100"><polygon points="50,2 93,27 93,73 50,98 7,73 7,27" fill="#1B4FBE" stroke="#0D3B8C" stroke-width="3"/><polyline points="35,58 50,46 65,58" fill="none" stroke="#FFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="35,48 50,36 65,48" fill="none" stroke="#FFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="35,38 50,26 65,38" fill="none" stroke="#FFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>
<div><div class="brand-name">REY CAPITAL</div><div class="brand-sub">PineScript Backtester Report</div></div></div>
<h1>Strategy Tester Report</h1>
<div class="settings"><span class="lbl">Strategy:</span><span class="val">${r.strategy_name||r.name}</span><span class="lbl">Symbol:</span><span class="val">${r.symbol}</span><span class="lbl">Period:</span><span class="val">${r.period}</span><span class="lbl">Initial Capital:</span><span class="val">${fmt(r.initial_capital)}</span><span class="lbl">Leverage:</span><span class="val">1:${r.leverage}</span><span class="lbl">Commission:</span><span class="val">${r.commission_pct}%</span></div>
${metricsHTML}<h2>Orders</h2>${ordersHTML}<h2>Deals</h2>${dealsHTML}<h2>Summary</h2>${summaryHTML}
<p style="margin-top:24px;font-size:0.75rem;color:${textMuted};text-align:center">Generated by Rey Capital PineScript Backtester</p></body></html>`;

    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `backtest_report_${r.symbol}.html`; a.click();
    URL.revokeObjectURL(url);
}

function buildMetricsHTML(m, accent, bgCard, border, text, textMuted, green, red) {
    const mr = (l, v, cv) => {
        let c = text;
        if (cv !== undefined) c = cv > 0 ? green : cv < 0 ? red : text;
        return `<div style="display:flex;justify-content:space-between;padding:6px 12px;font-size:0.8rem;border-bottom:1px solid ${border}"><span style="color:${textMuted}">${l}</span><span style="font-family:Consolas,monospace;font-weight:600;color:${c}">${v??'-'}</span></div>`;
    };
    return `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;border:1px solid ${border};border-radius:8px;overflow:hidden;margin-bottom:18px">
<div style="border-right:1px solid ${border}"><div style="background:${bgCard};padding:7px 12px;font-size:0.75rem;font-weight:700;color:${accent};text-transform:uppercase;border-bottom:1px solid ${border}">Performance</div>${mr('Total Net Profit',fmt(m.total_net_profit),m.total_net_profit)}${mr('Gross Profit',fmt(m.gross_profit),m.gross_profit)}${mr('Gross Loss',fmt(m.gross_loss),m.gross_loss)}${mr('Profit Factor',m.profit_factor?.toFixed(2))}${mr('Sharpe Ratio',m.sharpe_ratio?.toFixed(2))}</div>
<div style="border-right:1px solid ${border}"><div style="background:${bgCard};padding:7px 12px;font-size:0.75rem;font-weight:700;color:${accent};text-transform:uppercase;border-bottom:1px solid ${border}">Drawdown</div>${mr('Balance DD Max',`${fmt(m.balance_dd_maximal)} (${m.balance_dd_maximal_pct?.toFixed(2)}%)`,-m.balance_dd_maximal)}${mr('Equity DD Max',`${fmt(m.equity_dd_maximal)} (${m.equity_dd_maximal_pct?.toFixed(2)}%)`,-m.equity_dd_maximal)}<div style="background:${bgCard};padding:7px 12px;font-size:0.75rem;font-weight:700;color:${accent};text-transform:uppercase;border-bottom:1px solid ${border}">Consecutive</div>${mr('Max Wins',`${m.max_consecutive_wins} (${fmt(m.max_consecutive_wins_money)})`)}${mr('Max Losses',`${m.max_consecutive_losses} (${fmt(m.max_consecutive_losses_money)})`)}</div>
<div><div style="background:${bgCard};padding:7px 12px;font-size:0.75rem;font-weight:700;color:${accent};text-transform:uppercase;border-bottom:1px solid ${border}">Trades</div>${mr('Total Trades',m.total_trades)}${mr('Profit Trades',`${m.profit_trades} (${m.profit_trades_pct?.toFixed(2)}%)`)}${mr('Loss Trades',`${m.loss_trades} (${m.loss_trades_pct?.toFixed(2)}%)`)}${mr('Largest Profit',fmt(m.largest_profit_trade),m.largest_profit_trade)}${mr('Largest Loss',fmt(m.largest_loss_trade),m.largest_loss_trade)}</div></div>`;
}

function buildOrdersHTML(orders, accent, bgCard, border, text) {
    if (!orders.length) return `<p style="color:${text}">No orders</p>`;
    const th = `style="background:${bgCard};color:${accent};padding:8px 10px;text-align:left;font-size:0.72rem;text-transform:uppercase;border-bottom:2px solid ${accent}"`;
    const td = `style="padding:6px 10px;border-bottom:1px solid ${border};font-family:Consolas,monospace;font-size:0.76rem"`;
    return `<table style="width:100%;border-collapse:collapse"><thead><tr><th ${th}>Time</th><th ${th}>Order</th><th ${th}>Symbol</th><th ${th}>Type</th><th ${th}>Vol</th><th ${th}>Price</th><th ${th}>S/L</th><th ${th}>T/P</th><th ${th}>State</th><th ${th}>Comment</th></tr></thead><tbody>${orders.map(o=>`<tr><td ${td}>${o.open_time||''}</td><td ${td}>${o.order_num||''}</td><td ${td}>${o.symbol||''}</td><td ${td}>${o.type||''}</td><td ${td}>${o.volume||''}</td><td ${td}>${fmtPrice(o.price)}</td><td ${td}>${o.sl?fmtPrice(o.sl):''}</td><td ${td}>${o.tp?fmtPrice(o.tp):''}</td><td ${td}>${o.state||''}</td><td ${td}>${o.comment||''}</td></tr>`).join('')}</tbody></table>`;
}

function buildDealsHTML(deals, accent, bgCard, border, text, green, red) {
    if (!deals.length) return `<p style="color:${text}">No deals</p>`;
    const th = `style="background:${bgCard};color:${accent};padding:8px 10px;text-align:left;font-size:0.72rem;text-transform:uppercase;border-bottom:2px solid ${accent}"`;
    const td = `style="padding:6px 10px;border-bottom:1px solid ${border};font-family:Consolas,monospace;font-size:0.76rem"`;
    return `<table style="width:100%;border-collapse:collapse"><thead><tr><th ${th}>Time</th><th ${th}>Deal</th><th ${th}>Symbol</th><th ${th}>Type</th><th ${th}>Dir</th><th ${th}>Vol</th><th ${th}>Price</th><th ${th}>Order</th><th ${th}>Comm</th><th ${th}>Swap</th><th ${th}>Profit</th><th ${th}>Bal</th><th ${th}>Comment</th></tr></thead><tbody>${deals.map(d=>`<tr><td ${td}>${d.time||''}</td><td ${td}>${d.deal_num||''}</td><td ${td}>${d.symbol||''}</td><td ${td}>${d.type||''}</td><td ${td}>${d.direction||''}</td><td ${td}>${d.volume||''}</td><td ${td}>${fmtPrice(d.price)}</td><td ${td}>${d.order_num||''}</td><td ${td}>${d.commission?.toFixed(2)||'0'}</td><td ${td}>${d.swap?.toFixed(2)||'0'}</td><td style="padding:6px 10px;border-bottom:1px solid ${border};font-family:Consolas,monospace;font-size:0.76rem;color:${d.profit>0?green:d.profit<0?red:'inherit'}">${d.profit?.toFixed(2)||'0'}</td><td ${td}>${d.balance?.toFixed(2)||''}</td><td ${td}>${d.comment||''}</td></tr>`).join('')}</tbody></table>`;
}

// -- Helpers ------------------------------------------------------------------

function fmt(n) {
    if (n == null || isNaN(n)) return '-';
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPrice(n) {
    if (n == null || isNaN(n) || n === 0) return '';
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 5 });
}

// -- Init ---------------------------------------------------------------------
document.getElementById('end-date').valueAsDate = new Date();

// Restore saved theme preference (default: light)
const savedTheme = localStorage.getItem('rc-theme') || 'light';
setTheme(savedTheme);
