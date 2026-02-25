const fileInput = document.getElementById('fileInput');
const dropZone = document.getElementById('dropZone');
const selectedFiles = document.getElementById('selectedFiles');
const processBtn = document.getElementById('processBtn');
const previewBtn = document.getElementById('previewBtn');
const resultsBody = document.getElementById('resultsBody');
const themePicker = document.getElementById('themePicker');

const metricFiles = document.getElementById('metricFiles');
const metricHeaders = document.getElementById('metricHeaders');
const metricLumpsum = document.getElementById('metricLumpsum');
const metricRows = document.getElementById('metricRows');
const statusBox = document.getElementById('statusBox');

let currentFiles = [];

function setStatus(text, type = '') {
  statusBox.className = `status-box ${type}`.trim();
  statusBox.textContent = text;
}

function formatNum(v) {
  return new Intl.NumberFormat().format(v || 0);
}

function updateSelectedFilesText() {
  if (!currentFiles.length) {
    selectedFiles.textContent = 'No files selected.';
    return;
  }
  selectedFiles.textContent = currentFiles.map((f) => f.name).join(', ');
}

function resetTableWithMessage(message) {
  resultsBody.innerHTML = `<tr><td colspan="7" class="muted">${message}</td></tr>`;
}

function renderResults(payload) {
  metricFiles.textContent = formatNum(payload.totals.files_processed);
  metricHeaders.textContent = formatNum(payload.totals.total_headers);
  metricLumpsum.textContent = formatNum(payload.totals.total_lumpsum);
  metricRows.textContent = formatNum(payload.totals.total_output_rows);

  if (!payload.results.length) {
    resetTableWithMessage('No processed files yet.');
    return;
  }

  resultsBody.innerHTML = payload.results.map((item) => `
    <tr>
      <td>${item.input_file}</td>
      <td>${formatNum(item.distinct_rebates)}</td>
      <td>${formatNum(item.header_count)}</td>
      <td>${formatNum(item.lumpsum_count)}</td>
      <td>${formatNum(item.output_rows)}</td>
      <td>${formatNum(item.elapsed_ms)}</td>
      <td><a class="download-link" href="${item.download_url}">Download CSV</a></td>
    </tr>
  `).join('');
}

function setFiles(fileList) {
  currentFiles = Array.from(fileList || []).filter((file) => file.name.toLowerCase().endsWith('.csv'));
  updateSelectedFilesText();
}

['dragenter', 'dragover'].forEach((eventName) => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
});

['dragleave', 'drop'].forEach((eventName) => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
  });
});

dropZone.addEventListener('drop', (e) => {
  setFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
  setFiles(e.target.files);
});

processBtn.addEventListener('click', async () => {
  if (!currentFiles.length) {
    setStatus('Please select at least one CSV file.', 'error');
    return;
  }

  const formData = new FormData();
  currentFiles.forEach((file) => formData.append('files', file));

  processBtn.disabled = true;
  setStatus('Processing files...');

  try {
    const response = await fetch('/api/process', {
      method: 'POST',
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.detail?.message || payload?.detail || 'Processing failed.';
      throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
    }

    renderResults(payload);
    setStatus('Processing completed successfully.', 'success');
  } catch (err) {
    setStatus(`Error: ${err.message}`, 'error');
  } finally {
    processBtn.disabled = false;
  }
});

previewBtn.addEventListener('click', () => {
  renderResults({
    totals: {
      files_processed: 2,
      total_headers: 34,
      total_lumpsum: 410,
      total_output_rows: 444,
    },
    results: [
      {
        input_file: 'MM-Holiday-Promo-2025.csv',
        distinct_rebates: 21,
        header_count: 21,
        lumpsum_count: 260,
        output_rows: 281,
        elapsed_ms: 284.14,
        download_url: '#',
      },
      {
        input_file: 'Q4-Vendor-Billings.csv',
        distinct_rebates: 13,
        header_count: 13,
        lumpsum_count: 150,
        output_rows: 163,
        elapsed_ms: 181.43,
        download_url: '#',
      },
    ],
  });
  setStatus('Showing sample UI data for layout review.', 'success');
});

const savedTheme = localStorage.getItem('rebate-theme');
if (savedTheme) {
  document.documentElement.setAttribute('data-theme', savedTheme);
  themePicker.value = savedTheme;
}

themePicker.addEventListener('change', (e) => {
  const theme = e.target.value;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('rebate-theme', theme);
});

updateSelectedFilesText();
resetTableWithMessage('No processed files yet.');
