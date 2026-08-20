// ─── State ───────────────────────────────────────────────────────────────────
let socket = null;
let batchCount = 5;
let selectedProviders = ['FirebaseDirect', 'OTPSMS', 'UOTP', 'Grizzly', 'Tiger', 'MeowSMS', 'OTPDoctor'];
let speed = 'normal';
let orders = {};
let settingsData = {};
let providerChart = null;
let timelineChart = null;

// ─── Firebase Device State ────────────────────────────────────────────────────
const fbState = {
    devices: {},   // accountIdx -> [{id,name,battery,status,phone,lastSeen,...}]
    messages: {},  // accountIdx -> [{text,sender,time}]
    accounts: [],  // [{url, key}]
    loading: false,
    search: '',
    autoRefresh: null
};

const PROVIDERS = {
    FirebaseDirect: { name: 'Firebase Direct', service: 'firebase', dotClass: 'dot-jio' },
    OTPSMS:    { name: 'OTP SMS',   service: 'jio',   dotClass: 'dot-uotp' },
    UOTP:      { name: 'UOTP',      service: 'jio',   dotClass: 'dot-uotp' },
    Grizzly:   { name: 'Grizzly',   service: 'jio',   dotClass: 'dot-grizzly' },
    Tiger:     { name: 'Tiger SMS', service: 'mjo',   dotClass: 'dot-tiger' },
    MeowSMS:   { name: 'MeowSMS',   service: 'myjio', dotClass: 'dot-meowsms' },
    OTPDoctor: { name: 'OTP Doctor',service: '10549', dotClass: 'dot-otpdoctor' }
};

// ─── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
    renderProviders();
    initControls();
    initTabs();
    initModals();
});

// ─── Socket.IO ───────────────────────────────────────────────────────────────
function initSocket() {
    socket = io();

    socket.on('connect', () => {
        updateConnectionStatus('connected', 'Connected');
        addLog('Connected to server', 'info');
        socket.emit('get_balances');
    });
    socket.on('disconnect', () => {
        updateConnectionStatus('disconnected', 'Disconnected');
        addLog('Disconnected from server', 'error');
    });
    socket.on('balance_update', (data) => {
        for (const [provider, balance] of Object.entries(data)) {
            const el = document.getElementById(`balance-${provider}`);
            if (el) {
                if (provider === 'FirebaseDirect') {
                    // balance is "fb:total:online:offline"
                    if (typeof balance === 'string' && balance.startsWith('fb:')) {
                        const [, total, onl, off] = balance.split(':');
                        el.innerHTML = `
                            <div style="font-size:13px;font-weight:700;color:#4ade80">📱 ${total} devices</div>
                            <div style="font-size:10px;display:flex;gap:6px;margin-top:2px;justify-content:flex-end">
                                <span style="color:#4ade80">🟢 ${onl}</span>
                                <span style="color:#64748b">⚫ ${off}</span>
                            </div>`;
                    } else if (typeof balance === 'string' && balance.startsWith('devices:')) {
                        const count = balance.split(':')[1];
                        el.textContent = `📱 ${count} devices`;
                        el.style.color = '#4ade80';
                    } else {
                        el.textContent = '📱 checking...';
                    }
                } else {
                    el.textContent = balance !== null ? `₹${parseFloat(balance).toFixed(2)}` : 'Error';
                }
                el.classList.remove('loading');
            }
        }
    });
    socket.on('order_update', (data) => {
        orders[data.id] = data;
        updateTopStats();
        if (data.status === 'logged_in') {
            addLog(`✅ Successfully logged into ${data.phone} (${data.provider})!`, 'success');
            addJioLog(`✅ Successfully logged into ${data.phone} (${data.provider})!`, 'success');
        } else if (data.status === 'cancelled') {
            addLog(`❌ Cancelled ${data.phone} (${data.provider})`, 'error');
        }
        if (document.getElementById('tab-orders').classList.contains('active')) {
            renderOrders();
        }
    });

    socket.on('omkar_gen_log', (data) => {
        const c = document.getElementById('omkarGenLog');
        if (!c) return;
        const e = c.querySelector('.log-empty');
        if (e) e.remove();
        const el = document.createElement('div');
        el.className = `log-entry log-${data.level || 'info'}`;
        
        // Highlight emails with a pill-like style if they exist
        let htmlMsg = data.msg.replace(/\[([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)\]/g, '<span class="log-email">$1</span>');
        
        el.innerHTML = `<span class="log-time">${new Date().toLocaleTimeString()}</span> <span class="log-msg">${htmlMsg}</span>`;
        c.insertBefore(el, c.firstChild);
    });
    socket.on('number_update', (data) => {
        orders[data.id] = data;
        renderOrders();
        updateTopStats();
    });
    socket.on('number_remove', (data) => {
        delete orders[data.id];
        renderOrders();
        updateTopStats();
    });
    socket.on('stats_update', (data) => {
        document.getElementById('statFetched').textContent = data.fetched || 0;
        document.getElementById('statJio').textContent = data.jio || 0;
        document.getElementById('statOtp').textContent = data.otp || 0;
        document.getElementById('statLogin').textContent = data.login || 0;
    });
    socket.on('log', (data) => {
        addLog(data.message, data.level || 'info');
        
        // Mirror Jio-related activity to the Jio log
        if (data.message.includes('Jio verified') || 
            data.message.includes('OTP received') || 
            data.message.includes('Link extracted') || 
            data.message.includes('Extracted Gemini Link') ||
            data.message.includes('Successfully logged into')) {
            addJioLog(data.message, data.level || 'info');
        }
    });
    socket.on('sniping_started', () => {
        document.getElementById('startBtn').classList.add('hidden');
        document.getElementById('stopBtn').classList.remove('hidden');
        document.getElementById('forceStopBtn').classList.add('hidden');
        updateConnectionStatus('sniping', 'Sniping...');
    });
    socket.on('sniping_stopped', () => {
        document.getElementById('startBtn').classList.remove('hidden');
        document.getElementById('stopBtn').classList.add('hidden');
        document.getElementById('forceStopBtn').classList.add('hidden');
        updateConnectionStatus('connected', 'Connected');
    });

    // System stats
    socket.on('system_stats', (data) => {
        updateGauge('cpu', data.cpu);
        updateGauge('ram', data.ram_percent);
        if (data.omkar_data) {
            renderOmkarSidebar(data.omkar_data);
        }
        document.getElementById('browsersOpen').textContent = data.browsers_open || 0;
    });

    // Settings
    socket.on('settings_data', (data) => {
        settingsData = data;
        renderSettings();
    });
    socket.on('settings_saved', () => addLog('Settings saved successfully', 'success'));

    // Analytics
    socket.on('analytics_data', (data) => renderAnalytics(data));

    // Order detail
    socket.on('order_detail', (data) => renderOrderDetail(data));
}

// ─── Gauges ──────────────────────────────────────────────────────────────────
function updateGauge(type, value) {
    const fill = document.getElementById(`${type}Fill`);
    const valEl = document.getElementById(`${type}Value`);
    if (!fill || !valEl) return;

    const v = Math.min(100, Math.max(0, value));
    fill.setAttribute('stroke-dasharray', `${v}, 100`);
    valEl.textContent = Math.round(v);

    // Color shift based on load
    let color;
    if (v < 50) color = type === 'cpu' ? '#06b6d4' : '#8b5cf6';
    else if (v < 80) color = '#f59e0b';
    else color = '#ef4444';
    fill.style.stroke = color;
}

function renderOmkarSidebar(omkarData) {
    const container = document.getElementById('omkarKeysListWidget');
    if (!container) return;
    
    if (omkarData.length === 0) {
        container.innerHTML = '<div class="log-empty">No keys configured.</div>';
        return;
    }
    
    let html = '';
    omkarData.forEach((k, idx) => {
        const usage = k.usage;
        const max = k.max || 200;
        const pct = Math.min(100, Math.max(0, (usage / max) * 100));
        const remain = max - usage;
        
        let color, desc;
        if (pct < 50) { color = '#22c55e'; desc = `${remain} left`; }
        else if (pct < 80) { color = '#f59e0b'; desc = `${remain} left`; }
        else if (pct < 100) { color = '#ef4444'; desc = 'Low'; }
        else { color = '#dc2626'; desc = 'Exhausted'; }
        
        html += `
        <div class="omkar-key-item">
            <div class="omkar-key-info">
                <div class="omkar-key-label">${k.label}</div>
                <div class="omkar-key-desc" style="color: ${color}">${desc}</div>
            </div>
            <div class="gauge gauge-mini" title="${usage}/${max} Used">
                <svg viewBox="0 0 36 36" class="gauge-svg">
                    <path class="gauge-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
                    <path class="gauge-fill" stroke-dasharray="${pct}, 100" style="stroke: ${color};" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
                </svg>
                <div class="gauge-label"><span class="gauge-value" style="color: ${color}">${usage}</span></div>
            </div>
        </div>
        `;
    });
    
    container.innerHTML = html;
}

// ─── Providers ───────────────────────────────────────────────────────────────
function renderProviders() {
    const container = document.getElementById('providerList');
    container.innerHTML = '';
    for (const [key, prov] of Object.entries(PROVIDERS)) {
        const selected = selectedProviders.includes(key);
        const card = document.createElement('div');
        card.className = `provider-card ${selected ? 'selected' : ''}`;
        card.dataset.provider = key;
        card.innerHTML = `
            <div class="provider-checkbox"></div>
            <div class="provider-info">
                <div class="provider-name">${prov.name}</div>
                <div class="provider-service">Service: ${prov.service} • India</div>
            </div>
            <div class="provider-balance loading" id="balance-${key}">Loading...</div>
        `;
        card.addEventListener('click', () => {
            const idx = selectedProviders.indexOf(key);
            if (idx > -1) { selectedProviders.splice(idx, 1); card.classList.remove('selected'); }
            else { selectedProviders.push(key); card.classList.add('selected'); }
        });
        container.appendChild(card);
    }
}

// ─── Controls ────────────────────────────────────────────────────────────────
function initControls() {
    document.getElementById('countDown').addEventListener('click', () => {
        if (batchCount > 1) batchCount--;
        document.getElementById('batchCount').textContent = batchCount;
    });
    document.getElementById('countUp').addEventListener('click', () => {
        if (batchCount < 20) batchCount++;
        document.getElementById('batchCount').textContent = batchCount;
    });
    document.querySelectorAll('.speed-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            speed = btn.dataset.speed;
        });
    });
    document.getElementById('startBtn').addEventListener('click', () => {
        if (selectedProviders.length === 0) { addLog('Select at least one provider!', 'error'); return; }
        socket.emit('start_sniping', { providers: selectedProviders, batch_size: batchCount, speed: speed });
    });
    document.getElementById('stopBtn').addEventListener('click', () => {
        socket.emit('stop_sniping');
        document.getElementById('stopBtn').classList.add('hidden');
        document.getElementById('forceStopBtn').classList.remove('hidden');
    });
    document.getElementById('forceStopBtn').addEventListener('click', () => {
        socket.emit('force_stop_sniping');
        document.getElementById('forceStopBtn').textContent = "Force Stopping...";
        document.getElementById('forceStopBtn').disabled = true;
    });
    document.getElementById('killZombieBtn').addEventListener('click', () => {
        socket.emit('kill_zombie_browsers');
        const btn = document.getElementById('killZombieBtn');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="btn-icon-left">🧹</span> Killing...';
        btn.disabled = true;
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 3000);
    });
    document.getElementById('refreshBalances').addEventListener('click', () => {
        document.querySelectorAll('.provider-balance').forEach(el => { el.textContent = 'Loading...'; el.classList.add('loading'); });
        socket.emit('get_balances');
    });
    document.getElementById('clearLog').addEventListener('click', () => {
        document.getElementById('logContainer').innerHTML = '<div class="log-empty">No activity yet...</div>';
    });
    const clearJioLogBtn = document.getElementById('clearJioLog');
    if (clearJioLogBtn) {
        clearJioLogBtn.addEventListener('click', () => {
            document.getElementById('jioLogContainer').innerHTML = '<div class="log-empty">No Jio activity yet...</div>';
        });
    }
    document.getElementById('refreshOrders').addEventListener('click', () => socket.emit('get_orders'));

    // Get API Modal bindings
    const getApiModal = document.getElementById('getApiModal');
    document.getElementById('openGetApiModal').addEventListener('click', () => {
        getApiModal.classList.remove('hidden');
    });
    const closeGetApi = () => getApiModal.classList.add('hidden');
    document.getElementById('closeGetApiModal').addEventListener('click', closeGetApi);
    document.getElementById('cancelGetApiModal').addEventListener('click', closeGetApi);
    
    const submitBtn = document.getElementById('submitGetApiModal');
    const stopBtn = document.getElementById('stopGetApiModal');
    
    submitBtn.addEventListener('click', () => {
        const text = document.getElementById('outlookAccountsTextarea').value.trim();
        if (!text) {
            alert("Please paste Outlook accounts first.");
            return;
        }
        document.getElementById('omkarGenLog').innerHTML = '<div class="log-empty">Starting automation...</div>';
        const accounts = text.split('\n').filter(l => l.trim().length > 0);
        
        submitBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');
        socket.emit('generate_omkar_keys', { accounts });
    });
    
    stopBtn.addEventListener('click', () => {
        socket.emit('stop_omkar_generation');
        stopBtn.classList.add('hidden');
        submitBtn.classList.remove('hidden');
    });
    
    socket.on('omkar_gen_done', () => {
        stopBtn.classList.add('hidden');
        submitBtn.classList.remove('hidden');
    });

    // ChatGPT Login Modal bindings
    const chatGptModal = document.getElementById('chatGptModal');
    document.getElementById('openChatGptModal').addEventListener('click', () => {
        chatGptModal.classList.remove('hidden');
    });
    const closeChatGpt = () => chatGptModal.classList.add('hidden');
    document.getElementById('closeChatGptModal').addEventListener('click', closeChatGpt);
    document.getElementById('cancelChatGptModal').addEventListener('click', closeChatGpt);

    const submitChatGptBtn = document.getElementById('submitChatGptModal');
    const stopChatGptBtn = document.getElementById('stopChatGptModal');

    // Email Converter Modal bindings
    const emailConverterModal = document.getElementById('emailConverterModal');
    if (document.getElementById('openEmailConverterModal')) {
        document.getElementById('openEmailConverterModal').addEventListener('click', () => {
            emailConverterModal.classList.remove('hidden');
        });
    }
    const closeEmailConverter = () => emailConverterModal.classList.add('hidden');
    if (document.getElementById('closeEmailConverterModal')) {
        document.getElementById('closeEmailConverterModal').addEventListener('click', closeEmailConverter);
        document.getElementById('cancelEmailConverterModal').addEventListener('click', closeEmailConverter);
    }
    if (document.getElementById('convertEmailsBtn')) {
        document.getElementById('convertEmailsBtn').addEventListener('click', () => {
            const input = document.getElementById('emailConverterInput').value;
            const format = document.getElementById('emailConverterFormat').value;
            const lines = input.split('\n');
            const result = [];
            
            for (let line of lines) {
                line = line.trim();
                if (!line) continue;
                const parts = line.split('|');
                if (parts.length >= 4) {
                    const email = parts[0].trim();
                    const password = parts[1].trim();
                    const refreshToken = parts[2].trim();
                    const clientId = parts[3].trim();
                    
                    let link = format.replace(/{email}/g, email)
                                     .replace(/{password}/g, password)
                                     .replace(/{refresh_token}/g, refreshToken)
                                     .replace(/{client_id}/g, clientId);
                                     
                    result.push(`${email} | ${password} | ${link}`);
                }
            }
            document.getElementById('emailConverterOutput').value = result.join('\n');
        });
    }

    submitChatGptBtn.addEventListener('click', () => {
        const numTabsStr = document.getElementById('chatGptNumTabs').value.trim();
        const numTabs = parseInt(numTabsStr, 10);
        if (isNaN(numTabs) || numTabs < 1) {
            alert("Please enter a valid number of tabs.");
            return;
        }
        document.getElementById('chatGptLog').innerHTML = '<div class="log-empty">Starting login...</div>';
        
        submitChatGptBtn.classList.add('hidden');
        stopChatGptBtn.classList.remove('hidden');
        socket.emit('start_chatgpt_login', { num_tabs: numTabs });
    });

    stopChatGptBtn.addEventListener('click', () => {
        socket.emit('stop_chatgpt_login');
        stopChatGptBtn.classList.add('hidden');
        submitChatGptBtn.classList.remove('hidden');
    });

    socket.on('chatgpt_login_done', () => {
        stopChatGptBtn.classList.add('hidden');
        submitChatGptBtn.classList.remove('hidden');
    });

    socket.on('chatgpt_log', (data) => {
        const c = document.getElementById('chatGptLog');
        if (!c) return;
        const e = c.querySelector('.log-empty');
        if (e) e.remove();
        const el = document.createElement('div');
        el.className = `log-entry log-${data.level || 'info'}`;
        el.innerHTML = `<span class="log-time">${new Date().toLocaleTimeString()}</span> <span class="log-msg">${data.msg}</span>`;
        c.insertBefore(el, c.firstChild);
    });
}

// ─── Tabs ────────────────────────────────────────────────────────────────────
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const tab = document.getElementById(`tab-${btn.dataset.tab}`);
            if (tab) tab.classList.add('active');
            if (btn.dataset.tab === 'analytics') socket.emit('get_analytics');
            if (btn.dataset.tab === 'devices') {
                if (Object.keys(fbState.devices).length === 0) fetchAllFirebase();
            }
        });
    });
    // Firebase inner tabs
    document.querySelectorAll('.fb-inner-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.fb-inner-tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.fb-inner-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const el = document.getElementById(btn.dataset.fbtab);
            if (el) el.classList.add('active');
        });
    });
}

// ─── Modals ──────────────────────────────────────────────────────────────────
function initModals() {
    // Settings
    document.getElementById('openSettings').addEventListener('click', () => {
        socket.emit('get_settings');
        document.getElementById('settingsModal').classList.remove('hidden');
    });
    document.getElementById('closeSettings').addEventListener('click', () => {
        document.getElementById('settingsModal').classList.add('hidden');
    });
    document.getElementById('saveSettings').addEventListener('click', saveSettings);
    document.querySelectorAll('.modal-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.modal-tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.modal-tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`mtab-${btn.dataset.mtab}`).classList.add('active');
        });
    });
    document.getElementById('addOmkarKey').addEventListener('click', () => {
        addOmkarKeyRow('');
    });
    
    document.getElementById('addFirebaseUrl')?.addEventListener('click', () => {
        addFirebaseUrlRow('', '');
    });
    document.getElementById('fbRefreshBtn')?.addEventListener('click', fetchAllFirebase);
    document.getElementById('fbSearch')?.addEventListener('input', (e) => {
        fbState.search = e.target.value.toLowerCase();
        renderFbDeviceGrid();
    });

    // Order detail
    document.getElementById('closeDetail').addEventListener('click', () => {
        document.getElementById('orderDetailModal').classList.add('hidden');
    });

    // Close modals on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.classList.add('hidden');
        });
    });
}

// ─── Settings ────────────────────────────────────────────────────────────────
function renderSettings() {
    // Provider keys
    const provContainer = document.getElementById('providerSettings');
    provContainer.innerHTML = '';
    const providers = settingsData.providers || {};
    for (const [key, cfg] of Object.entries(providers)) {
        const card = document.createElement('div');
        card.className = 'provider-setting-card';

        // FirebaseDirect uses DB URLs (not API key/URL) — configured in "Firebase Links" tab
        if (key === 'FirebaseDirect') {
            card.innerHTML = `
                <div class="provider-setting-name">🔥 FirebaseDirect</div>
                <div class="setting-group" style="opacity:0.7;font-size:13px;padding:10px 0">
                    Firebase uses Realtime Database URLs, not an API key.<br>
                    ➜ Configure URLs in the <b>"Firebase Links"</b> tab above.
                </div>
            `;
            provContainer.appendChild(card);
            continue;
        }

        card.innerHTML = `
            <div class="provider-setting-name">${key}</div>
            <div class="setting-group">
                <label>API Key <button class="key-toggle" data-field="key-${key}">👁 Show</button></label>
                <input type="password" class="setting-input" id="key-${key}" value="${cfg.key || ''}" data-provider="${key}" data-field="key">
            </div>
            <div class="setting-group">
                <label>URL</label>
                <input type="text" class="setting-input" id="url-${key}" value="${cfg.url || ''}" data-provider="${key}" data-field="url">
            </div>
            <div class="setting-group">
                <label>Service / Country / Delay</label>
                <div class="setting-input-row">
                    <input type="text" class="setting-input" id="svc-${key}" value="${cfg.service || ''}" data-provider="${key}" data-field="service" placeholder="Service">
                    <input type="text" class="setting-input" id="cty-${key}" value="${cfg.country || ''}" data-provider="${key}" data-field="country" placeholder="Country" style="width:80px">
                    <input type="number" class="setting-input" id="dly-${key}" value="${cfg.delay || 3}" data-provider="${key}" data-field="delay" placeholder="Delay" style="width:80px">
                </div>
            </div>
        `;
        provContainer.appendChild(card);
    }

    // Key toggle listeners
    document.querySelectorAll('.key-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = document.getElementById(btn.dataset.field);
            if (input.type === 'password') { input.type = 'text'; btn.textContent = '🔒 Hide'; }
            else { input.type = 'password'; btn.textContent = '👁 Show'; }
        });
    });

    // Omkar keys
    const omkarList = document.getElementById('omkarKeysList');
    omkarList.innerHTML = '';
    (settingsData.omkar_keys || []).forEach(k => addOmkarKeyRow(k));
    
    // Firebase Accounts (url + optional key)
    const firebaseList = document.getElementById('firebaseUrlsList');
    if (firebaseList) {
        firebaseList.innerHTML = '';
        const accounts = settingsData.firebase_accounts;
        if (accounts && accounts.length > 0) {
            accounts.forEach(acc => addFirebaseUrlRow(acc.url || acc, acc.key || ''));
        } else {
            (settingsData.firebase_urls || []).forEach(url => addFirebaseUrlRow(url, ''));
        }
    }

    // Timing
    const timing = settingsData.timing || {};
    document.getElementById('settingPollInterval').value = timing.otp_poll_interval || 3;
    document.getElementById('settingCancelWait').value = timing.cancel_wait_seconds || 120;
    document.getElementById('settingMaxAttempts').value = timing.max_otp_attempts || 60;
}

function addOmkarKeyRow(value) {
    const list = document.getElementById('omkarKeysList');
    const row = document.createElement('div');
    row.className = 'setting-input-row';
    row.innerHTML = `
        <input type="password" class="setting-input omkar-key-input" value="${value}" placeholder="ok_...">
        <button class="key-toggle" onclick="this.previousElementSibling.type = this.previousElementSibling.type === 'password' ? 'text' : 'password'">👁</button>
        <button class="btn-remove-key" onclick="this.parentElement.remove()">✕</button>
    `;
    list.appendChild(row);
}

function addFirebaseUrlRow(url, key) {
    const list = document.getElementById('firebaseUrlsList');
    if (!list) return;
    const row = document.createElement('div');
    row.className = 'firebase-account-row';
    row.innerHTML = `
        <input type="text" class="setting-input firebase-url-input" value="${url || ''}" placeholder="https://project.firebaseio.com" style="flex:2">
        <input type="text" class="setting-input firebase-key-input" value="${key || ''}" placeholder="Auth key (optional)" style="flex:1;font-family:monospace;font-size:11px">
        <button class="btn-remove-key" onclick="this.parentElement.remove()">✕</button>
    `;
    list.appendChild(row);
}

function saveSettings() {
    const newConfig = { providers: {}, omkar_keys: [], firebase_urls: [], timing: {} };

    // Collect provider settings
    const providers = settingsData.providers || {};
    for (const key of Object.keys(providers)) {
        newConfig.providers[key] = {
            key: document.getElementById(`key-${key}`)?.value || '',
            url: document.getElementById(`url-${key}`)?.value || '',
            service: document.getElementById(`svc-${key}`)?.value || '',
            country: document.getElementById(`cty-${key}`)?.value || '',
            delay: parseInt(document.getElementById(`dly-${key}`)?.value || '3')
        };
    }

    // Omkar keys
    document.querySelectorAll('.omkar-key-input').forEach(input => {
        if (input.value.trim()) newConfig.omkar_keys.push(input.value.trim());
    });
    
    // Firebase Accounts (url + key pairs)
    newConfig.firebase_accounts = [];
    newConfig.firebase_urls = [];
    document.querySelectorAll('.firebase-account-row').forEach(row => {
        const url = row.querySelector('.firebase-url-input')?.value?.trim() || '';
        const key = row.querySelector('.firebase-key-input')?.value?.trim() || '';
        if (url) {
            newConfig.firebase_accounts.push({ url, key });
            newConfig.firebase_urls.push(url); // backward compat
        }
    });

    // Timing
    newConfig.timing = {
        otp_poll_interval: parseInt(document.getElementById('settingPollInterval').value),
        cancel_wait_seconds: parseInt(document.getElementById('settingCancelWait').value),
        max_otp_attempts: parseInt(document.getElementById('settingMaxAttempts').value)
    };

    socket.emit('save_settings', newConfig);
    document.getElementById('settingsModal').classList.add('hidden');
}

// ─── Order Rendering ─────────────────────────────────────────────────────────
function renderOrders() {
    const container = document.getElementById('ordersContainer');
    const ids = Object.keys(orders);
    document.getElementById('orderCount').textContent = ids.length;

    if (ids.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-icon">📡</div><h3>No active numbers</h3><p>Select providers and click "Start Sniping" to begin</p></div>`;
        return;
    }

    ids.sort((a, b) => {
        const pa = getStatusPriority(orders[a].status), pb = getStatusPriority(orders[b].status);
        if (pa !== pb) return pa - pb;
        return (orders[b].timestamp || 0) - (orders[a].timestamp || 0);
    });

    container.innerHTML = ids.map(id => renderOrderCard(orders[id])).join('');

    // Attach listeners
    container.querySelectorAll('.btn-cancel').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); socket.emit('cancel_number', { id: btn.dataset.id }); });
    });
    container.querySelectorAll('.btn-copy-otp').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(btn.dataset.otp);
            btn.textContent = '✓ Copied!';
            setTimeout(() => { btn.innerHTML = '📋 Copy'; }, 1500);
        });
    });
    container.querySelectorAll('.btn-repoll').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); socket.emit('request_new_otp', { id: btn.dataset.id }); });
    });
    container.querySelectorAll('.btn-force-cancel').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); socket.emit('force_cancel', { id: btn.dataset.id }); });
    });
    container.querySelectorAll('.order-card').forEach(card => {
        card.addEventListener('click', () => {
            const orderId = card.dataset.id;
            if (orders[orderId]) openOrderDetail(orders[orderId]);
        });
    });
}

function getStatusPriority(s) {
    return { extract_link:0, logged_in:1, logging_in:2, otp_received:3, waiting_otp:4, checking_carrier:5, cancelling:6, non_jio:7, cancelled:8 }[s] ?? 5;
}

function renderOrderCard(o) {
    const prov = PROVIDERS[o.provider] || {};
    const badge = getStatusBadge(o.status);
    const statusText = getStatusText(o.status);
    const progress = getProgress(o.status);
    const time = o.timestamp ? new Date(o.timestamp * 1000).toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' }) : '';
    const isActive = ['waiting_otp', 'checking_carrier', 'logging_in'].includes(o.status);
    const statusClass = getCardClass(o.status);

    let otp = o.otp ? `<div class="order-otp">${o.otp}</div>` : '';
    let actions = '';
    if (o.status !== 'cancelled' && o.status !== 'cancelling') {
        actions += `<button class="btn-cancel" data-id="${o.id}">🗑 Cancel</button>`;
    }
    if (o.status === 'cancelling' || o.status === 'non_jio') {
        actions += `<button class="btn-force-cancel" data-id="${o.id}">⚡ Force Cancel</button>`;
    }
    if (o.otp) actions += `<button class="btn-copy-otp" data-otp="${o.otp}">📋 Copy</button>`;
    if (['waiting_otp','otp_received'].includes(o.status)) {
        actions += `<button class="btn-repoll" data-id="${o.id}">🔄 Re-poll</button>`;
    }

    let timerHtml = '';
    if (['waiting_otp', 'cancelling', 'non_jio'].includes(o.status)) {
        let maxTime = (o.status === 'waiting_otp') ? 240 : 120;
        if (o.provider === 'OTPDoctor' && o.status !== 'waiting_otp') maxTime = 300;
        
        let startTime = o.timestamp;
        if (o.events && o.events.length > 0) {
            // Find the last major status event, or just use the last event
            startTime = o.events[o.events.length - 1].t;
        }
        
        timerHtml = `
            <div class="order-timer-container" data-start="${startTime}" data-max="${maxTime}">
                <svg class="order-timer-svg" viewBox="0 0 24 24">
                    <circle class="order-timer-bg" cx="12" cy="12" r="10"></circle>
                    <circle class="order-timer-fill" cx="12" cy="12" r="10"></circle>
                </svg>
            </div>
        `;
    }

    return `
        <div class="order-card ${statusClass}" data-id="${o.id}">
            ${timerHtml}
            <div class="order-top">
                <div class="order-phone-row">
                    <span class="order-phone">+${o.phone || '...'}</span>
                    <span class="order-badge ${badge.cls}">${badge.text}</span>
                </div>
                <span class="order-time">${time}</span>
            </div>
            <div class="order-meta">
                <span class="order-provider"><span class="provider-dot ${prov.dotClass || ''}"></span>${prov.name || o.provider}</span>
                ${o.carrier ? `<span>• ${o.carrier}</span>` : ''}
            </div>
            <div class="order-status-bar">
                <span class="status-text">${statusText}</span>
                ${isActive ? '<div class="status-dots"><span></span><span></span><span></span></div>' : ''}
                <div class="progress-bar"><div class="progress-fill" style="width:${progress}%"></div></div>
            </div>
            ${otp}
            <div class="order-actions">
                ${actions}
                <span class="order-id">#${(o.aid || '').slice(-6)}</span>
            </div>
        </div>`;
}

function getCardClass(s) {
    return { waiting_otp:'status-waiting-otp', otp_received:'status-jio', logging_in:'status-jio', logged_in:'status-login-success', extract_link:'status-login-success', non_jio:'status-non-jio', cancelling:'status-non-jio', cancelled:'status-non-jio' }[s] || '';
}
function getStatusBadge(s) {
    return { checking_carrier:{text:'Checking',cls:'badge-waiting-sms'}, waiting_otp:{text:'Waiting SMS',cls:'badge-waiting-sms'}, otp_received:{text:'OTP Received',cls:'badge-otp-received'}, logging_in:{text:'Logging In',cls:'badge-logging-in'}, logged_in:{text:'Logged In',cls:'badge-logged-in'}, extract_link:{text:'Extract Link',cls:'badge-extract'}, non_jio:{text:'Non-Jio',cls:'badge-non-jio'}, cancelling:{text:'Cancelling',cls:'badge-cancelling'}, cancelled:{text:'Cancelled',cls:'badge-non-jio'}, jio:{text:'Jio ✓',cls:'badge-jio'} }[s] || {text:s,cls:'badge-waiting-sms'};
}
function getStatusText(s) {
    return { checking_carrier:'Checking carrier via MNP...', waiting_otp:'Waiting for SMS', otp_received:'OTP received! Opening browser...', logging_in:'Logging into jio.com...', logged_in:'Successfully logged in!', extract_link:'⚡ Extract your link now!', non_jio:'Not Jio. Waiting to cancel & refund.', cancelling:'Cancelling & requesting refund...', cancelled:'Cancelled & refunded.' }[s] || s;
}
function getProgress(s) {
    return { checking_carrier:15, waiting_otp:40, otp_received:60, logging_in:75, logged_in:90, extract_link:100, non_jio:100, cancelling:50, cancelled:100 }[s] || 0;
}

// ─── Order Detail ────────────────────────────────────────────────────────────
function openOrderDetail(order) {
    document.getElementById('detailPhone').textContent = `+${order.phone}`;

    const prov = PROVIDERS[order.provider] || {};
    let metaHtml = `
        <span class="detail-meta-item">Provider: ${prov.name || order.provider}</span>
        <span class="detail-meta-item">Carrier: ${order.carrier || 'Unknown'}</span>
        <span class="detail-meta-item">Status: ${getStatusBadge(order.status).text}</span>
        <span class="detail-meta-item">AID: ${order.aid || 'N/A'}</span>
    `;
    document.getElementById('detailMeta').innerHTML = metaHtml;

    // OTP
    if (order.otp) {
        document.getElementById('detailOtp').innerHTML = `<div class="order-otp">${order.otp}</div>`;
    } else {
        document.getElementById('detailOtp').innerHTML = '';
    }

    // Timeline
    const events = order.events || [];
    let tlHtml = events.map(ev => {
        const t = new Date(ev.t * 1000).toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit', second:'2-digit' });
        return `<div class="timeline-entry"><span class="tl-time">${t}</span><span class="tl-msg">${ev.msg}</span></div>`;
    }).join('');
    document.getElementById('detailTimeline').innerHTML = tlHtml || '<div class="timeline-entry"><span class="tl-msg">No events recorded</span></div>';

    // Actions
    let actionsHtml = '';
    if (['waiting_otp','otp_received'].includes(order.status)) {
        actionsHtml += `<button class="btn-repoll" onclick="socket.emit('request_new_otp',{id:'${order.id}'})">🔄 Re-poll OTP</button>`;
    }
    if (order.status !== 'cancelled') {
        actionsHtml += `<button class="btn-force-cancel" onclick="socket.emit('force_cancel',{id:'${order.id}'}); document.getElementById('orderDetailModal').classList.add('hidden');">⚡ Force Cancel</button>`;
    }
    if (order.otp) {
        actionsHtml += `<button class="btn-copy-otp" onclick="navigator.clipboard.writeText('${order.otp}'); this.textContent='✓ Copied!'">📋 Copy OTP</button>`;
    }
    actionsHtml += `<button class="btn-copy-otp" onclick="navigator.clipboard.writeText(JSON.stringify(${JSON.stringify(safe(order))}, null, 2)); this.textContent='✓ Copied!'">📋 Copy All</button>`;
    document.getElementById('detailActions').innerHTML = actionsHtml;

    document.getElementById('orderDetailModal').classList.remove('hidden');
}

function safe(order) {
    const o = {};
    for (const [k,v] of Object.entries(order)) { if (!k.startsWith('_')) o[k] = v; }
    return o;
}

// ─── Analytics ───────────────────────────────────────────────────────────────
function renderAnalytics(data) {
    const events = data.events || [];
    renderProviderChart(events);
    renderTimelineChart(events);
    renderCostTable(events);
}

function renderProviderChart(events) {
    const stats = {};
    for (const p of Object.keys(PROVIDERS)) stats[p] = { fetched:0, jio:0, otp:0, login:0 };
    events.forEach(e => { if (stats[e.p] && stats[e.p][e.e] !== undefined) stats[e.p][e.e]++; });

    const labels = Object.keys(stats);
    const datasets = [
        { label:'Fetched', data: labels.map(l=>stats[l].fetched), backgroundColor:'rgba(59,130,246,0.7)' },
        { label:'Jio',     data: labels.map(l=>stats[l].jio),     backgroundColor:'rgba(34,197,94,0.7)' },
        { label:'OTP',     data: labels.map(l=>stats[l].otp),     backgroundColor:'rgba(6,182,212,0.7)' },
        { label:'Login',   data: labels.map(l=>stats[l].login),   backgroundColor:'rgba(139,92,246,0.7)' }
    ];

    const ctx = document.getElementById('providerChart');
    if (providerChart) providerChart.destroy();
    providerChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color:'#94a3b8', font:{size:11} } } },
            scales: {
                x: { ticks:{color:'#64748b'}, grid:{color:'#1e293b'} },
                y: { ticks:{color:'#64748b'}, grid:{color:'#1e293b'} }
            }
        }
    });
}

function renderTimelineChart(events) {
    // Group events into 30-min buckets over last 24h
    const now = Date.now() / 1000;
    const bucketSize = 1800; // 30 min
    const numBuckets = 48;
    const buckets = [];
    for (let i = numBuckets - 1; i >= 0; i--) {
        const t = now - i * bucketSize;
        buckets.push({ t, fetched:0, jio:0, otp:0 });
    }

    events.forEach(e => {
        if (e.t < now - numBuckets * bucketSize) return;
        const idx = Math.floor((e.t - (now - numBuckets * bucketSize)) / bucketSize);
        if (idx >= 0 && idx < numBuckets && buckets[idx]) {
            if (e.e === 'fetched') buckets[idx].fetched++;
            if (e.e === 'jio') buckets[idx].jio++;
            if (e.e === 'otp') buckets[idx].otp++;
        }
    });

    const labels = buckets.map(b => new Date(b.t * 1000).toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' }));

    const ctx = document.getElementById('timelineChart');
    if (timelineChart) timelineChart.destroy();
    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label:'Jio %', data: buckets.map(b => b.fetched > 0 ? Math.round(b.jio/b.fetched*100) : 0), borderColor:'#22c55e', backgroundColor:'rgba(34,197,94,0.1)', fill:true, tension:0.4 },
                { label:'OTP %', data: buckets.map(b => b.jio > 0 ? Math.round(b.otp/b.jio*100) : 0), borderColor:'#06b6d4', backgroundColor:'rgba(6,182,212,0.1)', fill:true, tension:0.4 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color:'#94a3b8', font:{size:11} } } },
            scales: {
                x: { ticks: { color:'#64748b', maxTicksLimit:8 }, grid: { color:'#1e293b' } },
                y: { ticks: { color:'#64748b', callback: v=>v+'%' }, grid: { color:'#1e293b' }, min:0, max:100 }
            }
        }
    });
}

function renderCostTable(events) {
    const stats = {};
    for (const p of Object.keys(PROVIDERS)) stats[p] = { fetched:0, jio:0, otp:0, login:0 };
    events.forEach(e => { if (stats[e.p] && stats[e.p][e.e] !== undefined) stats[e.p][e.e]++; });

    const table = document.getElementById('costTable');
    // Keep header, remove old rows
    table.querySelectorAll('.cost-row').forEach(r => r.remove());

    for (const [p, s] of Object.entries(stats)) {
        const jioP = s.fetched > 0 ? (s.jio/s.fetched*100).toFixed(1)+'%' : '0%';
        const otpP = s.jio > 0 ? (s.otp/s.jio*100).toFixed(1)+'%' : '0%';
        const row = document.createElement('div');
        row.className = 'cost-row';
        row.innerHTML = `<span>${p}</span><span>${s.fetched}</span><span>${s.jio}</span><span>${s.otp}</span><span>${s.login}</span><span>${jioP}</span><span>${otpP}</span>`;
        table.appendChild(row);
    }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function updateConnectionStatus(type, text) {
    const el = document.getElementById('connectionStatus');
    el.querySelector('.dot').className = `dot dot-${type}`;
    el.querySelector('span:last-child').textContent = text;
}

function addLog(message, level='info') {
    const container = document.getElementById('logContainer');
    if (!container) return;
    const empty = container.querySelector('.log-empty');
    if (empty) empty.remove();
    const entry = document.createElement('div');
    entry.className = `log-entry log-${level}`;
    const time = new Date().toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit', second:'2-digit' });
    entry.textContent = `[${time}] ${message}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
    while (container.children.length > 100) container.removeChild(container.firstChild);
}

function addJioLog(message, level='info') {
    const container = document.getElementById('jioLogContainer');
    if (!container) return;
    const empty = container.querySelector('.log-empty');
    if (empty) empty.remove();
    const entry = document.createElement('div');
    entry.className = `log-entry log-${level}`;
    const time = new Date().toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit', second:'2-digit' });
    entry.textContent = `[${time}] ${message}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
    while (container.children.length > 500) container.removeChild(container.firstChild); // Keep more history for Jio logs
}

function updateTopStats() {
    let fetched=0, jio=0, otp=0, login=0;
    for (const o of Object.values(orders)) {
        fetched++;
        if (['waiting_otp','otp_received','logging_in','logged_in','extract_link'].includes(o.status)) jio++;
        if (o.otp) otp++;
        if (['logged_in','extract_link'].includes(o.status)) login++;
    }
    document.getElementById('statFetched').textContent = fetched;
    document.getElementById('statJio').textContent = jio;
    document.getElementById('statOtp').textContent = otp;
    document.getElementById('statLogin').textContent = login;
}

// ─── Firebase Device Management ──────────────────────────────────────────────
function getFbAccounts() {
    if (settingsData.firebase_accounts && settingsData.firebase_accounts.length > 0)
        return settingsData.firebase_accounts;
    return (settingsData.firebase_urls || []).map(url => ({ url, key: '' }));
}

async function fetchAllFirebase() {
    const accounts = getFbAccounts();
    fbState.accounts = accounts;
    if (accounts.length === 0) {
        document.getElementById('fbDevicesEmpty').style.display = 'flex';
        document.getElementById('fbDeviceGrid').innerHTML = '';
        updateFbStats();
        return;
    }
    document.getElementById('fbDevicesEmpty').style.display = 'none';
    document.getElementById('fbRefreshBtn').textContent = '⟳';
    fbState.loading = true;

    await Promise.allSettled(accounts.map((acc, idx) => fetchFbAccount(acc, idx)));

    fbState.loading = false;
    document.getElementById('fbRefreshBtn').textContent = '↻';
    renderFbDeviceGrid();
    renderFbMessages();
    updateFbStats();
}

async function fetchFbAccount({ url, key }, idx) {
    if (!url || !url.trim()) return;
    const base = url.trim().replace(/\/$/, '');
    const auth = key ? `?auth=${encodeURIComponent(key)}` : '';
    try {
        const [cr, mr] = await Promise.allSettled([
            fetch(`${base}/clients.json${auth}`, { signal: AbortSignal.timeout(12000) }).then(r => r.ok ? r.json() : null),
            fetch(`${base}/messages.json${auth}`, { signal: AbortSignal.timeout(12000) }).then(r => r.ok ? r.json() : null)
        ]);
        fbState.devices[idx] = parseFbDevices(cr.status === 'fulfilled' ? cr.value : null);
        fbState.messages[idx] = parseFbMessages(mr.status === 'fulfilled' ? mr.value : null);
    } catch {
        fbState.devices[idx] = [];
        fbState.messages[idx] = [];
    }
}

function parseFbDevices(data) {
    if (!data || typeof data !== 'object') return [];
    return Object.entries(data).map(([id, d]) => {
        if (!d || typeof d !== 'object') return null;
        const sims = Array.isArray(d.sims) ? d.sims : (d.sims && typeof d.sims === 'object' ? Object.values(d.sims) : []);
        const battery = parseInt(String(d.battery || '0').replace('%', '')) || 0;
        const rawTs = d.lastSeen ?? d.last_seen ?? d.lastOnline ?? d.last_online ?? d.lastActive ?? d.timestamp ?? d.time ?? null;
        const lastSeen = parseTs(rawTs);
        return {
            id, battery,
            name: String(d.modelName || d.model || d.deviceName || id),
            batteryStr: String(d.battery || battery + '%'),
            status: !!d.status,
            phone: String(d.mobNo || (sims[0]?.phoneNumber ?? '—')),
            android: String(d.androidV || d.androidVersion || '—'),
            ip: String(d.ip_address || '—'),
            provider: String(d.service_provider || '—'),
            storage: String(d.storage || '—'),
            lastSeen,
            lastSeenStr: lastSeen ? timeAgo(lastSeen) : '—'
        };
    }).filter(Boolean).sort((a, b) => (b.status ? 1 : 0) - (a.status ? 1 : 0));
}

function parseFbMessages(data) {
    if (!data || typeof data !== 'object') return [];
    const msgs = [];
    Object.entries(data).forEach(([key, val]) => {
        if (!val || typeof val !== 'object') return;
        // Check if this is a device bucket (nested messages)
        const firstChild = Object.values(val)[0];
        if (firstChild && typeof firstChild === 'object' && !firstChild.message && !firstChild.body && !firstChild.text) {
            // Device bucket: {deviceId: {msgId: {message,...}}}
            Object.values(val).forEach(m => {
                if (!m || typeof m !== 'object') return;
                const text = String(m.message || m.body || m.text || '');
                if (text.trim()) msgs.push({ text, sender: String(m.sender || m.from || ''), time: String(m.dateTime || m.date || '') });
            });
        } else {
            const text = String(val.message || val.body || val.text || '');
            if (text.trim()) msgs.push({ text, sender: String(val.sender || val.from || ''), time: String(val.dateTime || val.date || '') });
        }
    });
    return msgs.slice(-150).reverse();
}

function parseTs(v) {
    if (!v) return null;
    if (typeof v === 'number') return v < 1e12 ? v * 1000 : v;
    if (typeof v === 'string') { const n = Date.parse(v); if (!isNaN(n)) return n; }
    return null;
}

function timeAgo(ms) {
    const d = Date.now() - ms;
    if (d < 0) return 'Just now';
    const s = Math.floor(d/1000), m = Math.floor(s/60), h = Math.floor(m/60), dy = Math.floor(h/24);
    if (s < 60) return s + 's ago';
    if (m < 60) return m + 'm ago';
    if (h < 24) return h + 'h ' + (m%60) + 'm ago';
    return dy + 'd ago';
}

function updateFbStats() {
    let totalDevices = 0, totalOnline = 0, totalMsgs = 0;
    Object.values(fbState.devices).forEach(devs => {
        totalDevices += devs.length;
        totalOnline += devs.filter(d => d.status).length;
    });
    Object.values(fbState.messages).forEach(msgs => { totalMsgs += msgs.length; });
    const offline = totalDevices - totalOnline;
    const dbs = fbState.accounts.length;

    document.getElementById('fbStatDbs').textContent = dbs;
    document.getElementById('fbStatTotal').textContent = totalDevices;
    document.getElementById('fbStatOnline').textContent = totalOnline;
    document.getElementById('fbStatOffline').textContent = offline;
    document.getElementById('fbStatMsgs').textContent = totalMsgs;

    // Update balance display for FirebaseDirect card
    const balEl = document.getElementById('balance-FirebaseDirect');
    if (balEl) {
        balEl.textContent = totalOnline > 0 ? `📱 ${totalOnline}/${totalDevices} online` : `📱 ${totalDevices} devices`;
        balEl.style.color = totalOnline > 0 ? '#4ade80' : '#94a3b8';
        balEl.classList.remove('loading');
    }
}

function renderFbDeviceGrid() {
    const grid = document.getElementById('fbDeviceGrid');
    const empty = document.getElementById('fbDevicesEmpty');
    if (!grid) return;

    const q = fbState.search;
    const allDevices = [];
    Object.entries(fbState.devices).forEach(([idx, devs]) => {
        const acc = fbState.accounts[parseInt(idx)];
        devs.forEach(d => allDevices.push({ ...d, accUrl: acc?.url || 'DB ' + idx }));
    });

    const filtered = q ? allDevices.filter(d =>
        d.name.toLowerCase().includes(q) || d.phone.includes(q) || d.id.toLowerCase().includes(q)
    ) : allDevices;

    if (filtered.length === 0) {
        empty.style.display = 'flex';
        grid.innerHTML = '';
        return;
    }
    empty.style.display = 'none';

    grid.innerHTML = filtered.map(d => {
        const battColor = d.battery >= 60 ? '#4ade80' : d.battery >= 30 ? '#facc15' : '#ef4444';
        const battWidth = Math.max(5, d.battery);
        const statusDot = d.status
            ? '<span class="fb-dot fb-dot-online"></span>'
            : '<span class="fb-dot fb-dot-offline"></span>';
        const lastSeenColor = d.status ? '#4ade80' : '#64748b';
        return `
        <div class="fb-device-card ${d.status ? 'fb-card-online' : 'fb-card-offline'}">
            <div class="fb-card-header">
                ${statusDot}
                <span class="fb-device-name" title="${d.id}">${d.name}</span>
                <div class="fb-battery" title="${d.batteryStr}">
                    <div class="fb-batt-body">
                        <div class="fb-batt-fill" style="width:${battWidth}%;background:${battColor}"></div>
                    </div>
                    <div class="fb-batt-tip"></div>
                    <span class="fb-batt-val" style="color:${battColor}">${d.battery}%</span>
                </div>
            </div>
            <div class="fb-card-phone">${d.phone}</div>
            <div class="fb-card-meta">
                <span title="Android version">🤖 ${d.android}</span>
                ${d.provider !== '—' ? `<span title="Carrier">📡 ${d.provider}</span>` : ''}
                ${d.ip !== '—' ? `<span title="IP">🌐 ${d.ip}</span>` : ''}
            </div>
            <div class="fb-card-footer" style="color:${lastSeenColor}">
                ${d.status ? '🟢 Online' : '⚫ ' + d.lastSeenStr}
            </div>
        </div>`;
    }).join('');
}

function renderFbMessages() {
    const container = document.getElementById('fbMsgsContainer');
    if (!container) return;
    const allMsgs = [];
    Object.values(fbState.messages).forEach(msgs => msgs.forEach(m => allMsgs.push(m)));
    if (allMsgs.length === 0) {
        container.innerHTML = '<div class="fb-empty">No messages found in Firebase</div>';
        return;
    }
    container.innerHTML = allMsgs.map(m => `
        <div class="fb-msg-item">
            <div class="fb-msg-sender">${m.sender || 'Unknown'}</div>
            <div class="fb-msg-text">${m.text}</div>
            ${m.time ? `<div class="fb-msg-time">${m.time}</div>` : ''}
        </div>
    `).join('');
}
