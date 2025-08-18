document.addEventListener('DOMContentLoaded', function() {
    // Batch Excel Import
    const importForm = document.getElementById('excelImportForm');
    const startImportBtn = document.getElementById('startImportBtn');
    const excelInput = document.getElementById('excel_file');
    const batchSizeSelect = document.getElementById('batch_size');
    const progressWrap = document.getElementById('importProgress');
    const progressBar = progressWrap ? progressWrap.querySelector('.progress-bar') : null;
    const importStatus = document.getElementById('importStatus');
    const importCounters = document.getElementById('importCounters');
    const errorsModalEl = document.getElementById('importErrorsModal');
    const errorsTableContainer = document.getElementById('errorsTableContainer');
    const errorsCloseBtn = document.getElementById('ieCloseBtn');
    const errorsCloseBtnFooter = document.getElementById('ieCloseBtnFooter');
    let allErrors = [];
    let excelColumns = [];

    function showMessage(text, type) {
        try {
            const adminMsgs = document.querySelector('#content-main .messagelist');
            if (adminMsgs) {
                const li = document.createElement('li');
                li.className = (type === 'success') ? 'success' : 'error';
                li.textContent = text;
                adminMsgs.appendChild(li);
                return;
            }
        } catch (e) {}
        alert(text);
    }

    async function runBatchImport(file, size) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

        if (progressWrap) { progressWrap.classList.remove('d-none'); }
        updateProgress(0, 0);
        setStatus('Başlayır...');
        setCounters(0,0,0,0);

        // init
        const formData = new FormData();
        formData.append('excel_file', file);
        // Reset errors UI/state
        allErrors = [];
        if (errorsTableContainer) errorsTableContainer.innerHTML = '';

        const initRes = await fetch('/my-products/import/init/', { method: 'POST', body: formData, credentials: 'include', headers: { 'X-CSRFToken': csrfToken } });
        const initData = await initRes.json();
        if (initData.status !== 'ok') throw new Error(initData.message || 'Başlatma xətası');
        const jobId = initData.job_id;
        const total = initData.total_rows || 0;
        let start = 0;

        // batch loop
        while (start < total) {
            const end = Math.min(start + size, total);
            setStatus(`Sətirlər: ${start}-${end}`);

            const body = new URLSearchParams({ job_id: jobId, start: String(start), size: String(size) });
            const batchRes = await fetch('/my-products/import/batch/', {
                method: 'POST',
                body,
                headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrfToken },
                credentials: 'include'
            });
            const data = await batchRes.json();
            if (data.status !== 'ok') throw new Error(data.message || 'Batch xətası');
            if (Array.isArray(data.columns) && data.columns.length) {
                excelColumns = data.columns;
            }

            const processed = data.processed_rows || end;
            const percent = total ? Math.round((processed / total) * 100) : 100;
            updateProgress(percent, processed);
            setCounters(data.new_count || 0, data.update_count || 0, data.error_count || 0, 0);
            if (Array.isArray(data.errors) && data.errors.length) {
                appendErrors(data.errors);
            }
            start += size;
        }

        // finalize
        const finRes = await fetch('/my-products/import/finalize/', {
            method: 'POST',
            body: new URLSearchParams({ job_id: jobId }),
            headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrfToken },
            credentials: 'include'
        });
        const finData = await finRes.json();
        if (finData.status !== 'ok') throw new Error(finData.message || 'Finalize xətası');
        if (Array.isArray(finData.columns) && finData.columns.length) {
            excelColumns = finData.columns;
        }
        setCounters(parseInt(importCounters.dataset.newCount || '0'), parseInt(importCounters.dataset.updateCount || '0'), parseInt(importCounters.dataset.errorCount || '0'), finData.deleted_count || 0);
        if (Array.isArray(finData.error_details) && finData.error_details.length) {
            appendErrors(finData.error_details);
        }
        setStatus('Tamamlandı');
    }

    function updateProgress(percent, processed) {
        if (!progressBar) return;
        progressBar.style.width = percent + '%';
        progressBar.setAttribute('aria-valuenow', percent);
        progressBar.textContent = percent + '%';
    }

    function setStatus(text) {
        if (importStatus) importStatus.textContent = text;
    }

    function setCounters(n, u, e, d) {
        importCounters.dataset.newCount = String(n);
        importCounters.dataset.updateCount = String(u);
        importCounters.dataset.errorCount = String(e);
        importCounters.dataset.deletedCount = String(d);
        if (e > 0) {
            importCounters.innerHTML = `Yeni: ${n} | Yenilənən: ${u} | Xəta: <a href="#" id="showErrorsLink">${e}</a>` + (d ? ` | Silinən: ${d}` : '');
            const link = document.getElementById('showErrorsLink');
            if (link) {
                link.addEventListener('click', function(ev) {
                    ev.preventDefault();
                    openErrorsModal();
                });
            }
        } else {
            importCounters.textContent = `Yeni: ${n} | Yenilənən: ${u} | Xəta: ${e}` + (d ? ` | Silinən: ${d}` : '');
        }
    }

    function appendErrors(list) {
        if (!list || !list.length) return;
        list.forEach(item => allErrors.push(item));
        renderErrorsTable();
    }

    function renderErrorsTable() {
        if (!errorsTableContainer) return;
        if (!allErrors.length) {
            errorsTableContainer.innerHTML = '<p class="text-muted">Xəta yoxdur.</p>';
            return;
        }

        // Excel sütunlarını təyin et
        const columns = (excelColumns && excelColumns.length) ? excelColumns : ['adi', 'kod', 'firma', 'qiymet', 'stok', 'kodlar'];
        
        // Xəta olan sətirləri sırala
        const lineToRow = {};
        const lineFieldErrors = {};
        allErrors.forEach(item => {
            if (item && item.line) {
                if (item.row) lineToRow[item.line] = item.row;
                const field = (item.field || '').toString().toLowerCase();
                if (!lineFieldErrors[item.line]) lineFieldErrors[item.line] = {};
                if (field) {
                    if (!lineFieldErrors[item.line][field]) lineFieldErrors[item.line][field] = [];
                    lineFieldErrors[item.line][field].push(item.message || 'Xəta');
                }
            }
        });

        const lines = Object.keys(lineToRow).map(n => parseInt(n)).sort((a,b)=>a-b);
        
        // Excel cədvəli yarat
        let tableHtml = '<table class="errors-table">';
        
        // Başlıq sətri
        tableHtml += '<thead><tr>';
        tableHtml += '<th class="line-number">Sətir</th>';
        columns.forEach(col => {
            tableHtml += `<th>${escapeHtml(col)}</th>`;
        });
        tableHtml += '<th>Xəta</th>';
        tableHtml += '</tr></thead>';
        
        // Məlumat sətirləri
        tableHtml += '<tbody>';
        lines.forEach(lineNo => {
            const row = lineToRow[lineNo] || {};
            const rowErrors = lineFieldErrors[lineNo] || {};
            
            tableHtml += '<tr class="error-row">';
            tableHtml += `<td class="line-number">${escapeHtml(lineNo)}</td>`;
            
            columns.forEach(col => {
                const key = col.toString().trim().toLowerCase();
                const val = (key in row) ? row[key] : '';
                const hasError = rowErrors[key] && rowErrors[key].length > 0;
                const cellClass = hasError ? 'error-cell' : '';
                const errorBadge = hasError ? `<span class="error-badge">✕</span>` : '';
                
                // kodlar sütunu üçün 25 simvoldan sonra ... əlavə et
                let displayVal = String(val || '');
                if (key === 'kodlar' && displayVal.length > 25) {
                    displayVal = displayVal.substring(0, 25) + '...';
                }
                
                tableHtml += `<td class="${cellClass}">${escapeHtml(displayVal)} ${errorBadge}</td>`;
            });
            
            // Xəta mesajları
            const allRowErrors = Object.values(rowErrors).flat();
            const errorText = allRowErrors.length > 0 ? allRowErrors.join('; ') : '';
            tableHtml += `<td>${escapeHtml(errorText)}</td>`;
            
            tableHtml += '</tr>';
        });
        tableHtml += '</tbody></table>';
        
        errorsTableContainer.innerHTML = tableHtml;
    }

    function openErrorsModal() {
        if (!errorsModalEl) return;
        renderErrorsTable();
        errorsModalEl.classList.add('is-open');
    }

    function closeErrorsModal() {
        if (!errorsModalEl) return;
        errorsModalEl.classList.remove('is-open');
    }

    if (errorsCloseBtn) errorsCloseBtn.addEventListener('click', closeErrorsModal);
    if (errorsCloseBtnFooter) errorsCloseBtnFooter.addEventListener('click', closeErrorsModal);
    if (errorsModalEl) errorsModalEl.addEventListener('click', function(e){ if (e.target === errorsModalEl) closeErrorsModal(); });

    function escapeHtml(unsafe) {
        return String(unsafe)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    if (startImportBtn && importForm) {
        startImportBtn.addEventListener('click', async function() {
            const file = excelInput?.files?.[0];
            if (!file) {
                showMessage('Zəhmət olmasa Excel faylı seçin.', 'error');
                return;
            }
            const size = parseInt(batchSizeSelect?.value || '100');
            startImportBtn.disabled = true;
            const original = startImportBtn.innerHTML;
            startImportBtn.innerHTML = 'Yüklənir...';
            try {
                await runBatchImport(file, size);
            } catch (err) {
                showMessage((err && err.message) ? err.message : 'İdxal zamanı xəta baş verdi', 'error');
            } finally {
                startImportBtn.disabled = false;
                startImportBtn.innerHTML = original;
            }
        });
    }
}); 