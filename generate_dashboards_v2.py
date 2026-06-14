import re
import shutil

with open('frontend/index.html', 'r') as f:
    base_html = f.read()

def generate_dashboard(mode_name, title_html, subtitle, port, primary_nav_path, controls_html, extra_panels_html, extra_js):
    html = base_html

    # Replace title
    html = re.sub(r'<h1>Port Knocking Dashboard</h1>', f'<h1>{title_html}</h1>', html)
    html = re.sub(r'<p class="subtitle">Dynamic firewall authentication</p>', f'<p class="subtitle">{subtitle}</p>', html)

    # Set active nav button
    html = html.replace('href="/" class="btn btn-primary"', 'href="/" class="btn btn-secondary"')
    html = html.replace(f'href="{primary_nav_path}" class="btn btn-secondary"', f'href="{primary_nav_path}" class="btn btn-primary"')

    # Inject controls
    html = html.replace('</section>\n      </div>\n\n      <section class="panel">', f'{controls_html}\n        </section>\n      </div>\n\n{extra_panels_html}\n      <section class="panel">')

    # Replace fetch logic
    fetch_api = f"""
  async function fetchAPI(endpoint, options = {{}}) {{
    const url = 'http://localhost:{port}' + endpoint;
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }}
"""
    
    # 1. Rewrite the entire refresh() function instead of regex
    
    refresh_js = f"""
  async function refresh() {{
    try {{
      const p = [
        fetchAPI('/api/status'),
        fetchAPI('/api/sessions'),
        fetchAPI('/api/logs?n=50')
      ];
      if ('{mode_name}' === 'ips') {{
        p.push(fetchAPI('/api/bans'));
        p.push(fetchAPI('/api/strikes'));
      }}
      const results = await Promise.all(p);
      renderStatus(results[0]);
      renderSessions(results[1].sessions);
      renderLogs(results[2].logs);
      if ('{mode_name}' === 'ips') {{
        renderBans(results[3].bans);
        renderStrikes(results[4].strikes);
      }}
    }} catch (e) {{
      console.error('Dashboard refresh failed', e);
    }}
  }}
"""

    # We need to completely overwrite the old refresh() in base_html.
    # The old refresh starts at `async function refresh() {` and ends before `function renderStatus`
    html = re.sub(r'async function refresh\(\) \{.*?(?=  function renderStatus)', refresh_js + '\n', html, flags=re.DOTALL)
    
    # 2. Rewrite simulateKnock to pass sequence dynamically
    sim_knock = """
  async function simulateKnock() {
    const host = document.getElementById('simHost').value || '127.0.0.1';
    let sequence;
    try {
        const st = await fetchAPI('/api/status');
        sequence = st.sequence;
    } catch(e) {}
    try {
      await fetchAPI('/api/knock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host, sequence })
      });
      showToast(`Knock sequence sent to ${host}`, false);
      refresh();
    } catch (e) {
      console.error('Simulate knock failed', e);
      showToast('Failed to send knock sequence', true);
    }
  }
"""
    html = re.sub(r'async function simulateKnock\(\) \{.*?(?=  async function updateSequence)', sim_knock + '\n', html, flags=re.DOTALL)


    # Replace other fetches inside testPort, updateSequence, revoke
    # First, change all remaining `fetch('/api/` to `fetchAPI('/api/`
    html = re.sub(r'fetch\(\'/api/', f"fetchAPI('/api/", html)
    # Inside those functions, `res.json()` is unwrapping the response, but fetchAPI already did.
    # So we change `const data = await res.json();` to nothing, and `const res = await fetchAPI` to `const data = await fetchAPI`
    html = re.sub(r'const data = await res\.json\(\);\s*', '', html)
    html = re.sub(r'const res = await fetchAPI', 'const data = await fetchAPI', html)
    
    html = html.replace('<script>', f'<script>\n{fetch_api}')
    html = html.replace('</script>', f'{extra_js}\n</script>')

    return html


# --- IPS ---
ips_controls = """
            <div class="control" style="border-color:rgba(184, 74, 69, 0.3); background:rgba(184, 74, 69, 0.05);">
              <label class="label" style="color:var(--danger);">Step 1 — Send Wrong Knock (triggers strikes)</label>
              <p style="font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:8px;">
                Knocks the specified <strong style="color:var(--danger)">wrong port sequence</strong>. Every wrong port knocked is 1 strike.<br>
                After 3 strikes → IP gets <strong style="color:var(--danger)">banned for 5 minutes</strong>.
              </p>
              <div class="field">
                <input type="text" id="wrongHost" value="127.0.0.1" placeholder="Target IP" style="flex: 0.4;">
                <input type="text" id="customWrongSeq" placeholder="e.g. 29000, 28000, 27000" style="flex: 0.6;">
                <button class="btn btn-danger" onclick="sendWrongKnock()" id="btnWrong" style="height:40px; font-size:13px;">
                  <svg viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
                  Send Wrong Knock
                </button>
              </div>
            </div>

            <div class="control">
              <label class="label">Step 2 — Send Correct Knock</label>
              <p style="font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:8px;">
                Knocks ports in the <strong style="color:var(--accent)">correct sequence</strong>.<br>
                If banned, connection will be instantly reset (TCP RST).
              </p>
              <div class="field">
                <input type="text" id="correctHost" value="127.0.0.1" placeholder="Target IP">
                <button class="btn btn-primary" onclick="sendCorrectKnock()" id="btnCorrect">
                  <svg viewBox="0 0 24 24" fill="none"><path d="M5 12h12M13 8l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  Send Correct Knock
                </button>
              </div>
            </div>
"""

ips_panels = """
      <section class="panel">
        <div class="panel-head" style="background:rgba(184, 74, 69, 0.05); border-bottom-color:rgba(184, 74, 69, 0.15);">
          <h2 class="panel-title" style="color:var(--danger);">Banned IPs</h2>
          <span class="panel-note">Currently blocked by IPS</span>
        </div>
        <div class="panel-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>IP Address</th>
                <th>Unban Time</th>
                <th>Remaining</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody id="bansBody"></tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title" style="color:var(--warn);">Strike Monitor</h2>
          <span class="panel-note">IPs approaching ban limit</span>
        </div>
        <div class="panel-body table-wrap" style="max-height: 200px; overflow: auto;">
          <table style="margin:0;">
            <thead>
              <tr>
                <th>IP Address</th>
                <th>Strikes</th>
              </tr>
            </thead>
            <tbody id="strikesBody"></tbody>
          </table>
        </div>
      </section>
"""

ips_js = """
  function renderBans(bans) {
    const tbody = document.getElementById('bansBody');
    if (!bans || bans.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4"><div class="empty">No banned IPs</div></td></tr>';
      return;
    }
    tbody.innerHTML = bans.map(b => {
      const remaining = b.remaining_seconds || 0;
      const ip = escapeHtml(b.ip);
      return `<tr>
          <td><span class="sequence-step" style="border-color:var(--danger); color:var(--danger);">${ip}</span></td>
          <td class="time">${escapeHtml(b.unban_at)}</td>
          <td class="remaining" style="color:var(--danger); font-weight:bold;">${remaining}s</td>
          <td><button class="btn btn-secondary" onclick="unban('${ip}')" style="height: 32px; padding: 0 10px; font-size: 12px;">Unban</button></td>
        </tr>`;
    }).join('');
  }

  function renderStrikes(strikes) {
    const tbody = document.getElementById('strikesBody');
    if (!strikes || strikes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="2"><div class="empty" style="min-height: 80px;">No strikes currently</div></td></tr>';
      return;
    }
    tbody.innerHTML = strikes.map(s => {
      const ip = escapeHtml(s.ip);
      const c = s.strikes;
      const m = s.max;
      
      let pips = '';
      for (let i = 0; i < m; i++) {
        let pipColor = i < c ? 'var(--danger)' : 'var(--surface-soft)';
        let pipBorder = i < c ? 'var(--danger)' : 'var(--line-strong)';
        pips += `<div style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; border: 2px solid ${pipBorder}; background: ${pipColor}; margin-right: 4px;"></div>`;
      }
      
      return `<tr>
          <td><span class="ip">${ip}</span></td>
          <td>
            <div style="display: flex; align-items: center; gap: 10px;">
              <span style="font-weight:bold; color:var(--danger);">${c}/${m}</span>
              <div style="display: flex; gap: 2px;">${pips}</div>
            </div>
          </td>
        </tr>`;
    }).join('');
  }

  async function unban(ip) {
      try {
          await fetchAPI('/api/unban', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip })
          });
          showToast(`Unbanned ${ip}`, false);
          refresh();
      } catch (e) {
          showToast('Failed to unban: ' + e.message, true);
      }
  }

  async function sendWrongKnock() {
    const host = document.getElementById('wrongHost').value.trim() || '127.0.0.1';
    let rawSeq = document.getElementById('customWrongSeq').value.trim();
    let wrongSeq;

    if (rawSeq) {
      wrongSeq = rawSeq.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n));
      if (wrongSeq.length === 0) {
        showToast('Enter valid port numbers (comma-separated)', true);
        return;
      }
    } else {
      try {
        const st = await fetchAPI('/api/status');
        const correct = st.sequence || [27000, 28000, 29000];
        wrongSeq = [...correct].reverse();
        if (JSON.stringify(wrongSeq) === JSON.stringify(correct)) {
            wrongSeq[0] = 27500;
        }
      } catch {
        wrongSeq = [29000, 28000, 27000];
      }
      document.getElementById('customWrongSeq').value = wrongSeq.join(', ');
    }

    try {
      await fetchAPI('/api/knock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host, sequence: wrongSeq, delay: 0.3 })
      });
      showToast(`Wrong knock sent: ${wrongSeq.join(' → ')}`, false);
      setTimeout(refresh, 1200);
    } catch (e) {
      showToast('Network error: ' + e.message, true);
    }
  }

  async function sendCorrectKnock() {
    const host = document.getElementById('correctHost').value.trim() || '127.0.0.1';
    let correctSeq;
    try {
      const st = await fetchAPI('/api/status');
      correctSeq = st.sequence || [27000, 28000, 29000];
    } catch {
      correctSeq = [27000, 28000, 29000];
    }

    try {
      await fetchAPI('/api/knock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host, sequence: correctSeq, delay: 0.3 })
      });
      showToast(`Correct knock sent: ${correctSeq.join(' → ')}`, false);
      setTimeout(refresh, 1200);
    } catch (e) {
      showToast('Network error: ' + e.message, true);
    }
  }
"""

ips_html = generate_dashboard(
    'ips', 
    "Port Knocking <span style='color: var(--danger);'>+ IPS</span>", 
    "Intrusion Prevention System & Ban Logic", 
    8081, 
    "/ips", 
    ips_controls, 
    ips_panels, 
    ips_js
)

with open('frontend/ips.html', 'w') as f:
    f.write(ips_html)
with open('demo_ips/frontend/index.html', 'w') as f:
    f.write(ips_html)


# --- TOTP ---
totp_js = """
  // TOTP specific status rendering override
  const originalRenderStatus = renderStatus;
  renderStatus = function(status) {
    originalRenderStatus(status);
    
    // Add TOTP specific UI
    let seqRow = document.querySelector('.status-row:first-child');
    if (status.totp && !document.getElementById('totpTimeContainer')) {
        let div = document.createElement('div');
        div.id = 'totpTimeContainer';
        div.style.marginTop = '8px';
        div.style.fontSize = '12px';
        div.style.color = 'var(--muted)';
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.justifyContent = 'space-between';
        
        div.innerHTML = `
          <span>Refreshes in <strong id="totpTime" style="color:var(--text);">--</strong>s</span>
          <div style="flex-grow: 1; height: 6px; background: var(--line-strong); border-radius: 3px; margin-left: 10px; overflow: hidden;">
            <div id="totpBar" style="height: 100%; width: 100%; background: var(--accent); transition: width 1s linear;"></div>
          </div>
        `;
        seqRow.appendChild(div);
    }
    
    if (status.totp && document.getElementById('totpTimeContainer')) {
        const remaining = status.totp.remaining_seconds;
        document.getElementById('totpTime').textContent = remaining;
        document.getElementById('totpBar').style.width = ((remaining / 30) * 100) + '%';
        if (remaining <= 5) {
            document.getElementById('totpBar').style.background = 'var(--danger)';
        } else if (remaining <= 10) {
            document.getElementById('totpBar').style.background = 'var(--warn)';
        } else {
            document.getElementById('totpBar').style.background = 'var(--accent)';
        }
    }
  };
"""

totp_html = generate_dashboard(
    'totp', 
    "Port Knocking <span style='color: var(--accent);'>+ TOTP</span>", 
    "Time-Based One-Time Sequences", 
    8082, 
    "/totp", 
    "", 
    "", 
    totp_js
)

with open('frontend/totp.html', 'w') as f:
    f.write(totp_html)
with open('demo_totp/frontend/index.html', 'w') as f:
    f.write(totp_html)


# --- GeoIP ---
geoip_js = """
  // GeoIP specific log rendering override
  const originalRenderLogs = renderLogs;
  renderLogs = function(logs) {
      originalRenderLogs(logs);
      
      // Inject location info into log rows
      const logRows = document.querySelectorAll('.log-entry');
      if (logRows.length > 0 && logs && logs.length > 0) {
          const reversed = logs.slice().reverse();
          logRows.forEach((row, i) => {
              if (reversed[i] && reversed[i].location) {
                  let loc = reversed[i].location;
                  let locSpan = document.createElement('span');
                  locSpan.className = 'sequence-step';
                  locSpan.style.marginLeft = '10px';
                  locSpan.style.fontSize = '10px';
                  locSpan.style.minHeight = '20px';
                  locSpan.textContent = typeof loc === 'string' ? loc : JSON.stringify(loc);
                  
                  // Color it based on if the backend gave it a warning/danger string,
                  // or just default to success color for valid locations
                  if (loc.includes('Unknown') || loc.includes('Blocked')) {
                      locSpan.style.borderColor = 'var(--danger)';
                      locSpan.style.color = 'var(--danger)';
                      locSpan.style.background = 'var(--danger-soft)';
                  } else {
                      locSpan.style.borderColor = 'var(--success)';
                      locSpan.style.color = 'var(--success)';
                      locSpan.style.background = 'var(--success-soft)';
                  }
                  row.querySelector('.log-ip').appendChild(locSpan);
              }
          });
      }
  };
"""

geoip_html = generate_dashboard(
    'geoip', 
    "Port Knocking <span style='color: var(--success);'>+ GeoIP</span>", 
    "Location-based Filtering", 
    8083, 
    "/geoip", 
    "", 
    "", 
    geoip_js
)

with open('frontend/geoip.html', 'w') as f:
    f.write(geoip_html)
with open('demo_geoip/frontend/index.html', 'w') as f:
    f.write(geoip_html)

print("Generated all dashboards with fixes.")
