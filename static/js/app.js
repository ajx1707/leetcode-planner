/**
 * app.js - Controller for LeetCode Scheduler & Daily Practice Planner
 * Clean monochrome architecture, real-time sync with Flask API & Excel tracker.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global State
  const state = {
    activeTab: 'analytics',
    currentPage: 1,
    totalPages: 1,
    problemsPerPage: 30,
    currentCompanyFilter: '',
    allTopics: [],
    topCompanies: []
  };

  function makeLeetCodeSlug(title) {
    return (title || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/['’]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function makeLeetCodeUrl(title, slug) {
    const s = slug || makeLeetCodeSlug(title);
    return `https://leetcode.com/problems/${s}/`;
  }

  function isStatusSolved(status) {
    if (!status) return false;
    const s = String(status).trim().toLowerCase();
    if (s.includes('unsolved')) return false;
    return s.includes('solved') || s.includes('done') || s.includes('complete');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // DOM References
  const navItems = document.querySelectorAll('.nav-item');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const toast = document.getElementById('appToast');

  // Modal References
  const logModal = document.getElementById('logModal');
  const btnOpenLogModal = document.getElementById('btnOpenLogModal');
  const btnCloseLogModal = document.getElementById('btnCloseLogModal');
  const btnCancelLogModal = document.getElementById('btnCancelLogModal');
  const formLogProgress = document.getElementById('formLogProgress');
  const logQuestionId = document.getElementById('logQuestionId');
  const logProblemSearch = document.getElementById('logProblemSearch');
  const logProblemDetails = document.getElementById('logProblemDetails');
  const logDate = document.getElementById('logDate');

  // Initialize
  initApp();

  function initApp() {
    setupTabNavigation();
    setupModals();
    setupFiltersAndSearch();
    setupSettingsButtons();

    // Default log date to today (YYYY-MM-DD)
    if (logDate) {
      logDate.value = new Date().toISOString().split('T')[0];
    }

    // Load initial data
    loadSystemStatus();
    loadAnalytics();
    loadDailyRecommendations();
    loadProblems();
    loadCompanies();
  }

  // Toast Notification
  function showToast(msg, duration = 2600) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, duration);
  }

  // Tab Navigation
  function setupTabNavigation() {
    navItems.forEach(tab => {
      tab.addEventListener('click', () => {
        const targetTab = tab.getAttribute('data-tab');
        state.activeTab = targetTab;

        navItems.forEach(t => t.classList.remove('active'));
        tabPanes.forEach(p => p.classList.remove('active'));

        tab.classList.add('active');
        const activePane = document.getElementById(`pane-${targetTab}`);
        if (activePane) activePane.classList.add('active');

        if (targetTab === 'analytics') loadAnalytics();
        if (targetTab === 'daily') loadDailyRecommendations(state.currentCompanyFilter);
        if (targetTab === 'explorer') loadProblems();
        if (targetTab === 'settings') loadSystemStatus();
      });
    });
  }

  // System Status & Settings
  async function loadSystemStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.success) {
        const badgeTelegram = document.getElementById('badgeTelegramStatus');
        const textReady = document.getElementById('textTelegramReady');
        if (badgeTelegram) {
          if (data.telegram_ready) {
            badgeTelegram.textContent = 'CONFIGURED';
            badgeTelegram.style.borderColor = '#10b981';
            badgeTelegram.style.color = '#10b981';
            if (textReady) {
              textReady.textContent = 'Active & Connected';
              textReady.style.color = '#10b981';
            }
          } else {
            badgeTelegram.textContent = 'MISSING ENV';
            badgeTelegram.style.borderColor = '#f59e0b';
            badgeTelegram.style.color = '#f59e0b';
            if (textReady) {
              textReady.textContent = 'Not Configured in Environment';
              textReady.style.color = '#f59e0b';
            }
          }
        }
      }
    } catch (err) {
      console.error('Failed to load status:', err);
    }
  }

  function setupSettingsButtons() {
    // Test Telegram Ping
    const btnTestTg = document.getElementById('btnTestTelegram');
    const tgFeedback = document.getElementById('telegramFeedback');

    if (btnTestTg) {
      btnTestTg.addEventListener('click', async () => {
        btnTestTg.disabled = true;
        btnTestTg.textContent = 'Testing...';
        try {
          const res = await fetch('/api/telegram/test', { method: 'POST' });
          const data = await res.json();
          if (tgFeedback) {
            tgFeedback.style.display = 'block';
            if (data.success) {
              tgFeedback.innerHTML = '<span style="color:#10b981;">✓ Test ping sent! Check your Telegram chat.</span>';
              showToast('Test ping sent to Telegram');
            } else {
              tgFeedback.innerHTML = `<span style="color:#ef4444;">✗ ${data.error || 'Failed to ping Telegram'}</span>`;
            }
          }
        } catch (e) {
          if (tgFeedback) tgFeedback.innerHTML = `<span style="color:#ef4444;">Error: ${e.message}</span>`;
        } finally {
          btnTestTg.disabled = false;
          btnTestTg.textContent = 'Test Ping';
        }
      });
    }

    // Send Practice Now button in Settings
    const btnSendPracticeTg = document.getElementById('btnSendPracticeTelegram');
    if (btnSendPracticeTg) {
      btnSendPracticeTg.addEventListener('click', async () => {
        btnSendPracticeTg.disabled = true;
        btnSendPracticeTg.textContent = 'Dispatching...';
        try {
          const res = await fetch('/api/telegram/send-daily', { method: 'POST' });
          const json = await res.json();
          if (tgFeedback) {
            tgFeedback.style.display = 'block';
            if (json.success) {
              tgFeedback.innerHTML = '<span style="color:#10b981;">✓ Daily practice batch dispatched to Telegram!</span>';
              showToast('Dispatched practice to Telegram');
            } else {
              tgFeedback.innerHTML = `<span style="color:#ef4444;">✗ ${json.error || 'Failed to dispatch'}</span>`;
            }
          }
        } catch (e) {
          showToast(`Error: ${e.message}`);
        } finally {
          btnSendPracticeTg.disabled = false;
          btnSendPracticeTg.textContent = 'Dispatch Practice Now';
        }
      });
    }

    // Trigger Morning Dispatch
    const btnTriggerMorn = document.getElementById('btnTriggerMorning');
    const btnTriggerEve = document.getElementById('btnTriggerEvening');
    const schedFeedback = document.getElementById('schedulerFeedback');

    if (btnTriggerMorn) {
      btnTriggerMorn.addEventListener('click', async () => {
        btnTriggerMorn.disabled = true;
        btnTriggerMorn.textContent = 'Dispatching...';
        try {
          const res = await fetch('/api/scheduler/trigger-morning', { method: 'POST' });
          const data = await res.json();
          if (schedFeedback) {
            schedFeedback.style.display = 'block';
            schedFeedback.innerHTML = data.success
              ? `<span style="color:#ffffff;">✓ Dispatched today's ${data.count} problem(s) to Telegram!</span>`
              : `<span style="color:#ef4444;">${data.error || 'Failed to dispatch'}</span>`;
          }
          showToast(data.success ? 'Morning batch dispatched to Telegram' : 'Dispatch failed');
          loadDailyRecommendations();
          loadAnalytics();
        } catch (e) {
          showToast(`Error: ${e.message}`);
        } finally {
          btnTriggerMorn.disabled = false;
          btnTriggerMorn.textContent = 'Trigger 9:00 AM Dispatch Now';
        }
      });
    }

    if (btnTriggerEve) {
      btnTriggerEve.addEventListener('click', async () => {
        btnTriggerEve.disabled = true;
        btnTriggerEve.textContent = 'Checking...';
        try {
          const res = await fetch('/api/scheduler/trigger-evening', { method: 'POST' });
          const data = await res.json();
          if (schedFeedback) {
            schedFeedback.style.display = 'block';
            if (data.success) {
              if (data.pending_count > 0) {
                schedFeedback.innerHTML = `<span style="color:#ffffff;">Reminder sent for ${data.pending_count} unfinished problem(s).</span>`;
              } else {
                schedFeedback.innerHTML = `<span style="color:#10b981;">✓ All problems completed! No reminder needed.</span>`;
              }
            } else {
              schedFeedback.innerHTML = `<span style="color:#ef4444;">${data.error || 'Failed check'}</span>`;
            }
          }
          showToast(data.success ? 'Evening check complete' : 'Reminder failed');
        } catch (e) {
          showToast(`Error: ${e.message}`);
        } finally {
          btnTriggerEve.disabled = false;
          btnTriggerEve.textContent = 'Trigger 7:00 PM Reminder Now';
        }
      });
    }

    // Reset Progress
    const btnResetProgress = document.getElementById('btnResetProgress');
    const resetFeedback = document.getElementById('resetFeedback');
    if (btnResetProgress) {
      btnResetProgress.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to reset all progress to 0 in leetcode_tracker.xlsx?')) {
          return;
        }
        btnResetProgress.disabled = true;
        btnResetProgress.textContent = 'Resetting...';
        try {
          const res = await fetch('/api/progress/reset', { method: 'POST' });
          const data = await res.json();
          if (data.success) {
            showToast('All progress reset to 0');
            if (resetFeedback) {
              resetFeedback.style.display = 'block';
              resetFeedback.innerHTML = '<span style="color:#ffffff;">✓ All progress reset to 0 in leetcode_tracker.xlsx.</span>';
            }
            loadAnalytics();
            loadDailyRecommendations();
            loadProblems();
          } else {
            showToast(`Error: ${data.error}`);
          }
        } catch (e) {
          showToast(`Reset failed: ${e.message}`);
        } finally {
          btnResetProgress.disabled = false;
          btnResetProgress.textContent = 'Reset All Progress to 0';
        }
      });
    }
  }

  // Analytics
  async function loadAnalytics() {
    try {
      const res = await fetch('/api/stats');
      const json = await res.json();
      if (!json.success) return;
      const stats = json.data;

      // Top Metrics
      const elTotal = document.getElementById('statTotalSolved');
      const elMaster = document.getElementById('statMasterTotal');
      const elRate = document.getElementById('statCompletionRate');
      const elFill = document.getElementById('statProgressFill');

      if (elTotal) elTotal.textContent = stats.total_solved;
      if (elMaster) elMaster.textContent = `/ ${stats.total_master.toLocaleString()}`;
      if (elRate) elRate.textContent = `${stats.completion_rate}% completion rate`;
      if (elFill) elFill.style.width = `${Math.min(stats.completion_rate, 100)}%`;

      document.getElementById('statIndepSolved').textContent = stats.solved_breakdown.independent;
      document.getElementById('statHintSolved').textContent = stats.solved_breakdown.with_hint;
      document.getElementById('statReviewSolved').textContent = stats.solved_breakdown.review_solved;

      document.getElementById('statReviewsDue').textContent = stats.reviews_due_count;

      // Difficulty Breakdown
      const diff = stats.difficulty_breakdown;
      const easyPct = diff.Easy.total > 0 ? (diff.Easy.solved / diff.Easy.total * 100).toFixed(1) : 0;
      const medPct = diff.Medium.total > 0 ? (diff.Medium.solved / diff.Medium.total * 100).toFixed(1) : 0;
      const hardPct = diff.Hard.total > 0 ? (diff.Hard.solved / diff.Hard.total * 100).toFixed(1) : 0;

      document.getElementById('diffEasyCounts').textContent = `${diff.Easy.solved} / ${diff.Easy.total}`;
      document.getElementById('diffEasyFill').style.width = `${easyPct}%`;

      document.getElementById('diffMedCounts').textContent = `${diff.Medium.solved} / ${diff.Medium.total}`;
      document.getElementById('diffMedFill').style.width = `${medPct}%`;

      document.getElementById('diffHardCounts').textContent = `${diff.Hard.solved} / ${diff.Hard.total}`;
      document.getElementById('diffHardFill').style.width = `${hardPct}%`;

      // Topics Grid
      const topicsContainer = document.getElementById('topicsContainer');
      document.getElementById('topicCountBadge').textContent = `${stats.topics.length} TOPICS`;

      if (stats.topics && stats.topics.length > 0) {
        state.allTopics = stats.topics.map(t => t.topic);
        populateTopicSelect(state.allTopics);

        topicsContainer.innerHTML = stats.topics.map(t => `
          <div class="topic-card">
            <div class="topic-row">
              <span class="topic-title">${escapeHtml(t.topic)}</span>
              <span class="topic-metric">${t.solved} / ${t.total} (<b>${t.percentage}%</b>)</span>
            </div>
            <div class="progress-track">
              <div class="progress-bar" style="width: ${Math.min(t.percentage, 100)}%"></div>
            </div>
          </div>
        `).join('');
      } else {
        topicsContainer.innerHTML = '<div class="empty-state">No topic records found.</div>';
      }

    } catch (err) {
      console.error('Error loading analytics:', err);
    }
  }

  // Today's Practice (Daily Batch)
  async function loadDailyRecommendations(company = '', regenerate = false) {
    const container = document.getElementById('dailyCardsContainer');
    if (!container) return;
    container.innerHTML = '<div class="loading-state">Loading today\'s practice assignment...</div>';

    try {
      const params = new URLSearchParams();
      if (company) params.set('company', company);
      if (regenerate) params.set('regenerate', 'true');

      const res = await fetch(`/api/daily?${params.toString()}`);
      const json = await res.json();
      if (!json.success) {
        container.innerHTML = `<div class="empty-state">Error: ${json.error}</div>`;
        return;
      }

      const recs = json.data;
      const dailyBadge = document.getElementById('dailyBadge');
      if (dailyBadge) dailyBadge.textContent = recs.length;

      if (!recs || recs.length === 0) {
        container.innerHTML = `
          <div class="daily-progress-banner" style="grid-column: 1 / -1; padding: 2.5rem 1.5rem; text-align: center; border-color: rgba(255,255,255,0.15);">
            <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">🎯</div>
            <h3 style="font-size: 1.25rem; margin-bottom: 0.5rem; color: #ffffff;">Ready for Today's Practice!</h3>
            <p style="color: #94a3b8; font-size: 0.9rem; max-width: 520px; margin: 0 auto 1.5rem auto; line-height: 1.5;">
              Practice problems are automatically dispatched at <b>9:00 AM IST</b>. You can also generate today's batch right now.
            </p>
            <button class="btn btn-primary btn-sm" onclick="window.regenerateDailyBatch()">
              Generate Today's Practice Now
            </button>
          </div>
        `;
        return;
      }

      const completedCount = recs.filter(r => isStatusSolved(r.status)).length;

      let bannerHtml = '';
      if (recs.length > 0 && completedCount === recs.length) {
        bannerHtml = `
          <div class="daily-progress-banner completed" style="grid-column: 1 / -1;">
            🎉 <b>Today's Assignment Complete!</b> You've solved all ${recs.length} assigned problem(s). Daily streak preserved!
          </div>
        `;
      } else {
        bannerHtml = `
          <div class="daily-progress-banner" style="grid-column: 1 / -1;">
            🎯 <b>Today's Assigned Problems:</b> ${completedCount} of ${recs.length} completed.
          </div>
        `;
      }

      const cardsHtml = recs.map(r => {
        const isCompleted = isStatusSolved(r.status);
        const cardClass = isCompleted ? 'daily-card completed-card' : 'daily-card';

        let badgeHtml = isCompleted
          ? `<span class="mono-badge completed-badge">✓ SOLVED TODAY</span>`
          : `<span class="mono-badge">${r.type || 'NEW'}</span>`;

        let compChips = '';
        if (r.companies) {
          const comps = r.companies.split(',').slice(0, 3);
          compChips = comps.map(c => `<span class="company-chip">${escapeHtml(c.trim())}</span>`).join('');
        }

        const problemUrl = r.url || makeLeetCodeUrl(r.title, r.slug);

        return `
          <div class="${cardClass}">
            <div class="daily-card-top">
              ${badgeHtml}
              <span class="tag">${escapeHtml(r.difficulty)}</span>
            </div>

            <h3 class="daily-card-title">
              <a href="${problemUrl}" target="_blank" rel="noopener noreferrer">
                #${r.question_id} ${escapeHtml(r.title)} ↗
              </a>
            </h3>

            <div class="daily-card-meta">
              <span class="topic-tag">${escapeHtml(r.topic)}</span>
              ${compChips}
            </div>

            <div class="daily-card-actions">
              <a href="${problemUrl}" target="_blank" class="btn btn-secondary btn-sm">Solve on LC ↗</a>
              ${isCompleted
                ? `<button class="btn btn-secondary btn-sm" disabled style="opacity:0.7;">✓ Completed</button>`
                : `<button class="btn btn-primary btn-sm" onclick="window.markQuickComplete('${r.question_id}')">✓ Mark Done</button>`
              }
              <button class="btn btn-secondary btn-sm" onclick="window.openLogModalForProblem('${r.question_id}', '${escapeHtml(r.title)}')">
                Log Details
              </button>
            </div>
          </div>
        `;
      }).join('');

      container.innerHTML = bannerHtml + cardsHtml;

    } catch (err) {
      container.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
    }
  }

  // Quick mark complete
  window.markQuickComplete = async function(qid) {
    try {
      const res = await fetch('/api/daily/mark-complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question_id: qid })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Problem #${qid} marked as completed!`);
        loadDailyRecommendations(state.currentCompanyFilter);
        loadAnalytics();
        loadProblems();
      } else {
        showToast(data.error || 'Failed to update');
      }
    } catch (e) {
      showToast(`Error: ${e.message}`);
    }
  };

  window.regenerateDailyBatch = function() {
    loadDailyRecommendations(state.currentCompanyFilter, true);
    showToast('Generated fresh practice batch for today');
  };

  // Daily company filter buttons
  const dailyFilterBtns = document.querySelectorAll('.filter-btn');
  dailyFilterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      dailyFilterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const comp = btn.getAttribute('data-company');
      state.currentCompanyFilter = comp;
      loadDailyRecommendations(comp);
    });
  });

  const btnRefreshDaily = document.getElementById('btnRefreshDaily');
  if (btnRefreshDaily) {
    btnRefreshDaily.addEventListener('click', () => {
      window.regenerateDailyBatch();
    });
  }

  const btnTelegramSendDaily = document.getElementById('btnTelegramSendDaily');
  if (btnTelegramSendDaily) {
    btnTelegramSendDaily.addEventListener('click', async () => {
      btnTelegramSendDaily.disabled = true;
      try {
        const res = await fetch('/api/telegram/send-daily', { method: 'POST' });
        const json = await res.json();
        if (json.success) {
          showToast('Practice batch dispatched to Telegram!');
        } else {
          showToast(json.error || 'Failed to dispatch');
        }
      } catch (e) {
        showToast(`Error: ${e.message}`);
      } finally {
        btnTelegramSendDaily.disabled = false;
      }
    });
  }

  // Problem Explorer
  async function loadProblems() {
    const tbody = document.getElementById('problemsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="loading-state">Loading problems...</td></tr>';

    const search = document.getElementById('inputSearch')?.value || '';
    const topic = document.getElementById('selectTopic')?.value || 'all';
    const diff = document.getElementById('selectDifficulty')?.value || 'all';
    const comp = document.getElementById('selectCompany')?.value || 'all';
    const status = document.getElementById('selectStatus')?.value || 'all';

    const params = new URLSearchParams({
      search: search,
      topic: topic,
      difficulty: diff,
      company: comp,
      status: status,
      page: state.currentPage,
      per_page: state.problemsPerPage
    });

    try {
      const res = await fetch(`/api/problems?${params.toString()}`);
      const json = await res.json();
      if (!json.success) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Error: ${json.error}</td></tr>`;
        return;
      }

      const { total, page, total_pages, items } = json.data;
      state.totalPages = total_pages || 1;

      document.getElementById('paginationInfo').textContent = `Showing ${items.length} of ${total} problems`;
      document.getElementById('pageIndicator').textContent = `Page ${page} / ${state.totalPages}`;
      document.getElementById('btnPrevPage').disabled = page <= 1;
      document.getElementById('btnNextPage').disabled = page >= state.totalPages;

      if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-state">No matching problems found.</td></tr>';
        return;
      }

      tbody.innerHTML = items.map(p => {
        const stLower = (p.status || 'unsolved').toLowerCase();
        let statusTag = '<span class="tag" style="color:var(--text-muted);">UNSOLVED</span>';

        if (isStatusSolved(stLower)) {
          statusTag = '<span class="mono-badge">SOLVED</span>';
        } else if (stLower.includes('attempt')) {
          statusTag = '<span class="tag">ATTEMPTED</span>';
        }

        let compsHtml = '';
        if (p.companies) {
          const comps = p.companies.split(',').slice(0, 3);
          compsHtml = comps.map(c => `<span class="company-chip">${escapeHtml(c.trim())}</span>`).join('');
          if (p.companies.split(',').length > 3) {
            compsHtml += `<span class="company-chip">+${p.companies.split(',').length - 3}</span>`;
          }
        }

        const problemUrl = p.url || makeLeetCodeUrl(p.title, p.slug);
        const isSolved = isStatusSolved(p.status);

        return `
          <tr>
            <td class="table-qid">#${p.question_id}</td>
            <td class="table-title">
              <a href="${problemUrl}" target="_blank" rel="noopener noreferrer" class="problem-title-link">
                ${escapeHtml(p.title)} <span style="font-size:0.72rem;opacity:0.5;">↗</span>
              </a>
            </td>
            <td><span class="tag">${p.difficulty}</span></td>
            <td>${escapeHtml(p.topic)}</td>
            <td>${compsHtml || '<span style="color:var(--text-muted);">-</span>'}</td>
            <td>${statusTag}</td>
            <td style="text-align: right;">
              ${isSolved
                ? `<span style="font-size:0.75rem; color:#10b981; margin-right:8px;">✓ Done</span>`
                : `<button class="btn btn-secondary btn-sm" onclick="window.markQuickComplete('${p.question_id}')" style="margin-right:4px;">Done</button>`
              }
              <button class="btn btn-secondary btn-sm" onclick="window.openLogModalForProblem('${p.question_id}', '${escapeHtml(p.title)}')">
                Log
              </button>
            </td>
          </tr>
        `;
      }).join('');

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Failed to load: ${err.message}</td></tr>`;
    }
  }

  function setupFiltersAndSearch() {
    let debounceTimer = null;
    const inputSearch = document.getElementById('inputSearch');
    if (inputSearch) {
      inputSearch.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          state.currentPage = 1;
          loadProblems();
        }, 280);
      });
    }

    ['selectTopic', 'selectDifficulty', 'selectCompany', 'selectStatus'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', () => {
          state.currentPage = 1;
          loadProblems();
        });
      }
    });

    document.getElementById('btnPrevPage')?.addEventListener('click', () => {
      if (state.currentPage > 1) {
        state.currentPage--;
        loadProblems();
      }
    });

    document.getElementById('btnNextPage')?.addEventListener('click', () => {
      if (state.currentPage < state.totalPages) {
        state.currentPage++;
        loadProblems();
      }
    });
  }

  async function loadCompanies() {
    try {
      const res = await fetch('/api/companies');
      const json = await res.json();
      if (json.success && json.data) {
        state.topCompanies = json.data;
        const sel = document.getElementById('selectCompany');
        if (sel) {
          sel.innerHTML = '<option value="all">All Companies</option>' +
            json.data.map(c => `<option value="${escapeHtml(c.company.toLowerCase())}">${escapeHtml(c.company)} (${c.count})</option>`).join('');
        }
      }
    } catch (e) {
      console.error('Error loading companies:', e);
    }
  }

  function populateTopicSelect(topics) {
    const sel = document.getElementById('selectTopic');
    if (!sel || sel.children.length > 1) return;
    sel.innerHTML = '<option value="all">All Topics</option>' +
      topics.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join('');
  }

  // Problem Logging Modal
  function setupModals() {
    btnOpenLogModal?.addEventListener('click', () => openLogModal());
    btnCloseLogModal?.addEventListener('click', closeLogModal);
    btnCancelLogModal?.addEventListener('click', closeLogModal);

    logModal?.addEventListener('click', (e) => {
      if (e.target === logModal) closeLogModal();
    });

    let lookupTimer = null;
    logProblemSearch?.addEventListener('input', () => {
      clearTimeout(lookupTimer);
      lookupTimer = setTimeout(async () => {
        const val = logProblemSearch.value.trim();
        if (!val) {
          logProblemDetails.textContent = '';
          return;
        }
        try {
          const res = await fetch(`/api/problem/${encodeURIComponent(val)}`);
          const json = await res.json();
          if (json.success && json.data) {
            logQuestionId.value = json.data.question_id;
            logProblemDetails.textContent = `Selected: #${json.data.question_id} ${json.data.title} (${json.data.difficulty} - ${json.data.topic})`;
            logProblemDetails.style.color = '#ffffff';
          } else {
            logProblemDetails.textContent = 'Problem not found in catalog';
            logProblemDetails.style.color = '#888888';
          }
        } catch (e) {
          logProblemDetails.textContent = '';
        }
      }, 300);
    });

    formLogProgress?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const qid = logQuestionId.value.trim() || logProblemSearch.value.trim();
      if (!qid) {
        showToast('Specify a Question ID');
        return;
      }

      const payload = {
        question_id: qid,
        status: document.getElementById('logStatus').value,
        attempt_date: document.getElementById('logDate').value,
        time_taken: document.getElementById('logTimeSpent').value || null,
        hints_used: document.getElementById('logHintsUsed').value || 0,
        feedback: document.getElementById('logFeedback').value.trim()
      };

      const btnSub = document.getElementById('btnSubmitLog');
      btnSub.disabled = true;
      btnSub.textContent = 'Saving...';

      try {
        const res = await fetch('/api/progress/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.success) {
          closeLogModal();
          showToast(`Problem #${qid} saved to tracker!`);
          loadAnalytics();
          loadDailyRecommendations(state.currentCompanyFilter);
          loadProblems();
        } else {
          showToast(`Error: ${json.error}`);
        }
      } catch (e) {
        showToast(`Save failed: ${e.message}`);
      } finally {
        btnSub.disabled = false;
        btnSub.textContent = 'Save to Tracker';
      }
    });
  }

  function openLogModal(qid = '', title = '') {
    if (qid) {
      logQuestionId.value = qid;
      logProblemSearch.value = `#${qid} ${title}`;
      logProblemDetails.textContent = `Selected: #${qid} ${title}`;
      logProblemDetails.style.color = '#ffffff';
    } else {
      logQuestionId.value = '';
      logProblemSearch.value = '';
      logProblemDetails.textContent = '';
    }
    const logDateEl = document.getElementById('logDate');
    if (logDateEl && !logDateEl.value) {
      logDateEl.value = new Date().toISOString().split('T')[0];
    }
    document.getElementById('logFeedback').value = '';
    logModal.classList.add('open');
  }

  function closeLogModal() {
    logModal.classList.remove('open');
  }

  window.openLogModalForProblem = function(qid, title) {
    openLogModal(qid, title);
  };
});
