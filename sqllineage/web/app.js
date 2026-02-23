/* ============================================================
   SQL Lineage Tracker — Frontend Application
   Hierarchical DAG + Column-Level Lineage
   ============================================================ */

(function () {
  'use strict';

  /* ---------- STATE ---------- */
  let uploadedFiles = [];
  let graphData = null;
  let svg, svgGroup, zoom;
  let showColumns = true;
  let currentHighlight = null;

  /* ---------- PALETTE ---------- */
  const LAYER_COLORS = {
    'raw': { fill: '#3B82F6', bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.25)', label: 'Source / Raw' },
    'staging': { fill: '#06B6D4', bg: 'rgba(6,182,212,0.08)', border: 'rgba(6,182,212,0.25)', label: 'Staging' },
    'intermediate': { fill: '#8B5CF6', bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.25)', label: 'Intermediate' },
    'mart': { fill: '#10B981', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.25)', label: 'Mart / Analytics' },
    'default': { fill: '#6C7BFF', bg: 'rgba(108,123,255,0.08)', border: 'rgba(108,123,255,0.25)', label: 'Other' },
  };
  const NODE_TYPE_ICONS = { table: '⊞', view: '◎', cte: '↻' };

  /* ---------- LAYOUT CONSTANTS ---------- */
  const NODE_W = 210;
  const HEADER_H = 40;
  const COL_ROW_H = 36;
  const LAYER_GAP_X = 320;
  const NODE_GAP_Y = 20;
  const LAYER_PAD = 30;
  const TOP_OFFSET = 80;

  /* ---------- DOM ---------- */
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileList = document.getElementById('file-list');
  const dialectSelect = document.getElementById('dialect-select');
  const columnToggle = document.getElementById('column-toggle');
  const analyzeBtn = document.getElementById('analyze-btn');
  const emptyState = document.getElementById('empty-state');
  const loadingState = document.getElementById('loading-state');
  const graphSvg = document.getElementById('lineage-graph');
  const graphControls = document.getElementById('graph-controls');
  const searchBar = document.getElementById('search-bar');
  const searchInput = document.getElementById('search-input');
  const statsSection = document.getElementById('stats-section');
  const detailSection = document.getElementById('detail-section');
  const nodeDetails = document.getElementById('node-details');

  /* ================================================================
     INIT
     ================================================================ */
  async function init() {
    setupEventListeners();
    await loadDialects();
  }

  async function loadDialects() {
    try {
      const res = await fetch('/api/dialects');
      const data = await res.json();
      data.dialects.forEach(d => {
        const o = document.createElement('option');
        o.value = d;
        o.textContent = d.charAt(0).toUpperCase() + d.slice(1);
        dialectSelect.appendChild(o);
      });
    } catch (e) { console.warn('Could not load dialects:', e); }
  }

  function setupEventListeners() {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFiles(e.dataTransfer.files); });
    fileInput.addEventListener('change', e => { handleFiles(e.target.files); fileInput.value = ''; });
    analyzeBtn.addEventListener('click', analyzeLineage);
    columnToggle.addEventListener('change', () => { showColumns = columnToggle.checked; if (graphData) renderGraph(graphData); });
    document.getElementById('zoom-in-btn').addEventListener('click', () => svgGroup && d3.select(graphSvg).transition().duration(300).call(zoom.scaleBy, 1.4));
    document.getElementById('zoom-out-btn').addEventListener('click', () => svgGroup && d3.select(graphSvg).transition().duration(300).call(zoom.scaleBy, 0.7));
    document.getElementById('zoom-fit-btn').addEventListener('click', fitToView);
    document.getElementById('export-png-btn').addEventListener('click', exportPNG);
    document.getElementById('export-json-btn').addEventListener('click', exportJSON);
    searchInput.addEventListener('input', handleSearch);
    const lcb = document.getElementById('legend-close-btn');
    if (lcb) lcb.addEventListener('click', () => document.getElementById('graph-legend').style.display = 'none');
  }

  /* ================================================================
     FILE HANDLING
     ================================================================ */
  function handleFiles(files) {
    for (const f of files) if (!uploadedFiles.find(u => u.name === f.name)) uploadedFiles.push(f);
    renderFileList();
    analyzeBtn.disabled = uploadedFiles.length === 0;
  }
  function removeFile(i) { uploadedFiles.splice(i, 1); renderFileList(); analyzeBtn.disabled = !uploadedFiles.length; }
  function renderFileList() {
    fileList.innerHTML = '';
    uploadedFiles.forEach((f, i) => {
      const d = document.createElement('div');
      d.className = 'file-item';
      d.innerHTML = `<span class="file-name"><svg class="file-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>${f.name}</span><button class="remove-btn" title="Remove"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
      d.querySelector('.remove-btn').addEventListener('click', () => removeFile(i));
      fileList.appendChild(d);
    });
  }

  /* ================================================================
     API — always fetches columns
     ================================================================ */
  async function analyzeLineage() {
    if (!uploadedFiles.length) return;
    emptyState.style.display = 'none'; graphSvg.style.display = 'none';
    graphControls.style.display = 'none'; searchBar.style.display = 'none';
    loadingState.style.display = 'flex';
    const fd = new FormData();
    uploadedFiles.forEach(f => fd.append('files', f));
    if (dialectSelect.value) fd.append('dialect', dialectSelect.value);
    fd.append('include_columns', 'true');
    try {
      const res = await fetch('/api/analyze', { method: 'POST', body: fd });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      graphData = await res.json();
      showColumns = columnToggle.checked;
      renderGraph(graphData);
      updateStats(graphData.stats);
      showToast(`Analyzed ${graphData.files.length} file(s) — ${graphData.stats.total_tables} tables found`, 'success');
    } catch (err) {
      console.error(err);
      showToast(`Error: ${err.message}`, 'error');
      loadingState.style.display = 'none'; emptyState.style.display = 'flex';
    }
  }
  function updateStats(s) {
    document.getElementById('stat-tables').textContent = s.total_tables;
    document.getElementById('stat-columns').textContent = s.total_columns;
    document.getElementById('stat-table-edges').textContent = s.table_edges;
    document.getElementById('stat-col-edges').textContent = s.column_edges;
    statsSection.style.display = 'block';
  }

  /* ================================================================
     LAYER DETECTION
     ================================================================ */
  function getLayerKey(n) {
    const id = (n.id || '').toLowerCase(), schema = (n.schema || '').toLowerCase(), name = (n.name || '').toLowerCase();
    if (/^raw/.test(schema)) return 'raw';
    if (/^stg|^staging/.test(schema)) return 'staging';
    if (/^int|^intermediate/.test(schema)) return 'intermediate';
    if (/^mart|^analytics/.test(schema)) return 'mart';
    if (/^raw[_.]/.test(name)) return 'raw';
    if (/^stg[_.]|^staging/.test(name)) return 'staging';
    if (/^int_/.test(name)) return 'intermediate';
    if (/^(mart|dim|fct|fact)_/.test(name)) return 'mart';
    if (/^raw\./.test(id)) return 'raw';
    if (/^(stg|staging)\./.test(id)) return 'staging';
    if (/^(int|intermediate)\./.test(id)) return 'intermediate';
    if (/^(mart|analytics)\./.test(id)) return 'mart';
    return 'default';
  }
  function getNodeColor(n) { return LAYER_COLORS[getLayerKey(n)] || LAYER_COLORS['default']; }

  /* ================================================================
     BUILD COLUMN MAP & EXPRESSION MAP
     Handles schema-qualified vs unqualified table IDs
     ================================================================ */

  // Resolve tableId: try exact, then try stripping schema prefix
  function resolveTableId(id, allTableIds) {
    if (allTableIds.has(id)) return id;
    // Try adding known schema prefixes
    for (const prefix of ['raw.', 'staging.', 'intermediate.', 'mart.', 'analytics.', 'stg.']) {
      if (allTableIds.has(prefix + id)) return prefix + id;
    }
    // Try stripping schema prefix
    const dot = id.indexOf('.');
    if (dot >= 0) {
      const base = id.substring(dot + 1);
      if (allTableIds.has(base)) return base;
    }
    return id;
  }

  function buildColumnMap(data) {
    const allTableIds = new Set(data.nodes.filter(n => n.level === 'table').map(n => n.id));
    const colMap = {};
    // From column nodes
    (data.nodes || []).forEach(n => {
      if (n.level === 'column') {
        const tid = resolveTableId(n.table || n.table_id || '', allTableIds);
        if (!colMap[tid]) colMap[tid] = new Set();
        colMap[tid].add(n.name);
      }
    });
    // From column edges
    (data.links || []).forEach(l => {
      if (l.type === 'column_to_column') {
        if (l.source_table && l.source_column) {
          const tid = resolveTableId(l.source_table, allTableIds);
          if (!colMap[tid]) colMap[tid] = new Set();
          colMap[tid].add(l.source_column);
        }
        if (l.target_table && l.target_column) {
          const tid = resolveTableId(l.target_table, allTableIds);
          if (!colMap[tid]) colMap[tid] = new Set();
          colMap[tid].add(l.target_column);
        }
      }
    });
    const result = {};
    Object.keys(colMap).forEach(k => { result[k] = [...colMap[k]].sort(); });
    return result;
  }

  function buildExprMap(data) {
    const allTableIds = new Set(data.nodes.filter(n => n.level === 'table').map(n => n.id));
    const exprMap = {};
    (data.links || []).forEach(l => {
      if (l.type === 'column_to_column' && l.expression && l.target_table && l.target_column) {
        const tid = resolveTableId(l.target_table, allTableIds);
        if (!exprMap[tid]) exprMap[tid] = {};
        if (!exprMap[tid][l.target_column]) {
          let expr = l.expression;
          const asIdx = expr.toLowerCase().lastIndexOf(' as ');
          if (asIdx > 0) expr = expr.substring(0, asIdx).trim();
          exprMap[tid][l.target_column] = expr;
        }
      }
    });
    return exprMap;
  }

  // Normalize column edges to use graph table IDs
  function normalizeColEdges(data) {
    const allTableIds = new Set(data.nodes.filter(n => n.level === 'table').map(n => n.id));
    return (data.links || []).filter(l => l.type === 'column_to_column').map(l => ({
      ...l,
      source_table: l.source_table ? resolveTableId(l.source_table, allTableIds) : '',
      target_table: l.target_table ? resolveTableId(l.target_table, allTableIds) : '',
    }));
  }

  /* ================================================================
     NODE HEIGHT
     ================================================================ */
  function getNodeH(node, colMap) {
    if (!showColumns || !colMap[node.id] || !colMap[node.id].length) return HEADER_H;
    return HEADER_H + colMap[node.id].length * COL_ROW_H + 8;
  }

  /* ================================================================
     HIERARCHICAL LAYOUT
     ================================================================ */
  function computeLayout(nodes, links, colMap) {
    const tableNodes = nodes.filter(n => n.level !== 'column');
    const tableLinks = links.filter(l => l.type === 'table_to_table');
    const inE = {}, outE = {};
    tableNodes.forEach(n => { inE[n.id] = []; outE[n.id] = []; });
    tableLinks.forEach(l => {
      const s = l.source, t = l.target;
      if (s === t) return;
      if (inE[t]) inE[t].push(s);
      if (outE[s]) outE[s].push(t);
    });
    const depth = {}, vis = {};
    function setDepth(id, d) {
      if (vis[id] && depth[id] >= d) return;
      vis[id] = true; depth[id] = Math.max(depth[id] || 0, d);
      (outE[id] || []).forEach(t => { if (t !== id) setDepth(t, d + 1); });
    }
    tableNodes.filter(n => !(inE[n.id] || []).filter(s => s !== n.id).length).forEach(r => setDepth(r.id, 0));
    tableNodes.forEach(n => { if (depth[n.id] === undefined) setDepth(n.id, 0); });

    const layers = {};
    tableNodes.forEach(n => { const d = depth[n.id] || 0; if (!layers[d]) layers[d] = []; layers[d].push(n); });
    const sortedDepths = Object.keys(layers).map(Number).sort((a, b) => a - b);
    const lo = ['raw', 'staging', 'intermediate', 'mart', 'default'];
    sortedDepths.forEach(d => {
      layers[d].sort((a, b) => { const la = lo.indexOf(getLayerKey(a)), lb = lo.indexOf(getLayerKey(b)); return la !== lb ? la - lb : a.name.localeCompare(b.name); });
    });

    sortedDepths.forEach((d, ci) => {
      const nl = layers[d];
      let totalH = 0;
      nl.forEach(n => { n._h = getNodeH(n, colMap); totalH += n._h + NODE_GAP_Y; });
      totalH -= NODE_GAP_Y;
      let y = TOP_OFFSET + Math.max(0, (600 - totalH) / 2);
      nl.forEach(n => { n.x = LAYER_PAD + ci * LAYER_GAP_X; n.y = y; n._depth = d; y += n._h + NODE_GAP_Y; });
    });

    const layerGroups = sortedDepths.map((d, ci) => {
      const nl = layers[d]; if (!nl.length) return null;
      const cc = {}; nl.forEach(n => { const k = getLayerKey(n); cc[k] = (cc[k] || 0) + 1; });
      const dk = Object.entries(cc).sort((a, b) => b[1] - a[1])[0][0];
      const colors = LAYER_COLORS[dk] || LAYER_COLORS['default'];
      const minY = Math.min(...nl.map(n => n.y)), maxY = Math.max(...nl.map(n => n.y + n._h));
      return { x: LAYER_PAD + ci * LAYER_GAP_X - 16, y: minY - 28, width: NODE_W + 32, height: (maxY - minY) + 48, label: colors.label, colors };
    }).filter(Boolean);

    return { tableNodes, layerGroups };
  }

  /* ================================================================
     RENDER GRAPH
     ================================================================ */
  function renderGraph(data) {
    d3.select(graphSvg).selectAll('*').remove();
    loadingState.style.display = 'none';
    graphSvg.style.display = 'block'; graphControls.style.display = 'flex'; searchBar.style.display = 'flex';
    const legend = document.getElementById('graph-legend');
    if (legend) legend.style.display = 'block';

    const w = graphSvg.parentElement.clientWidth, h = graphSvg.parentElement.clientHeight;
    svg = d3.select(graphSvg).attr('width', w).attr('height', h);
    zoom = d3.zoom().scaleExtent([0.08, 3]).on('zoom', ev => svgGroup.attr('transform', ev.transform));
    svg.call(zoom);
    svg.on('click', ev => { if (ev.target === graphSvg) clearHighlight(); });
    svgGroup = svg.append('g');

    const colMap = buildColumnMap(data);
    const exprMap = buildExprMap(data);
    const columnLinks = normalizeColEdges(data);
    const links = data.links.filter(l => l.source !== l.target).map(l => ({ ...l }));
    const tableLinks = links.filter(l => l.type === 'table_to_table');
    const { tableNodes, layerGroups } = computeLayout(data.nodes, links, colMap);
    const nodeMap = {}; tableNodes.forEach(n => { nodeMap[n.id] = n; });

    // === DEFS ===
    const defs = svgGroup.append('defs');
    [
      ['arr', 'rgba(255,255,255,0.2)', 8, 'M0,-5L10,0L0,5'],
      ['arr-hl', '#60A5FA', 8, 'M0,-5L10,0L0,5'],
      ['arr-col', 'rgba(251,191,36,0.5)', 6, 'M0,-3L7,0L0,3'],
      ['arr-col-hl', '#FBBF24', 6, 'M0,-3L7,0L0,3'],
    ].forEach(([id, color, size, path]) => {
      defs.append('marker').attr('id', id).attr('viewBox', `0 -${size} ${size * 1.5} ${size * 2}`)
        .attr('refX', size * 1.2).attr('refY', 0).attr('markerWidth', size).attr('markerHeight', size)
        .attr('orient', 'auto').append('path').attr('d', path).attr('fill', color);
    });

    // === LAYER BACKGROUNDS ===
    const lbg = svgGroup.append('g');
    layerGroups.forEach(lg => {
      const g = lbg.append('g');
      g.append('rect').attr('x', lg.x).attr('y', lg.y).attr('width', lg.width).attr('height', lg.height)
        .attr('rx', 12).attr('fill', lg.colors.bg).attr('stroke', lg.colors.border).attr('stroke-width', 1).attr('stroke-dasharray', '4,3');
      g.append('text').attr('x', lg.x + lg.width / 2).attr('y', lg.y + 16)
        .attr('text-anchor', 'middle').attr('font-size', '10px').attr('font-weight', '600')
        .attr('letter-spacing', '1px').attr('fill', lg.colors.fill).attr('opacity', 0.7)
        .text(lg.label.toUpperCase());
    });

    // === TABLE EDGES ===
    const le = svgGroup.append('g').selectAll('path').data(tableLinks).enter().append('path')
      .attr('class', 'link-path')
      .attr('d', d => { const s = nodeMap[d.source], t = nodeMap[d.target]; return s && t ? edgePath(s, t, s._h, t._h) : ''; })
      .attr('fill', 'none').attr('stroke', 'rgba(255,255,255,0.12)').attr('stroke-width', 2).attr('marker-end', 'url(#arr)');

    // === COLUMN EDGES ===
    let cle = null;
    if (showColumns && columnLinks.length) {
      cle = svgGroup.append('g').selectAll('path').data(columnLinks).enter().append('path')
        .attr('class', 'col-link-path')
        .attr('d', d => colEdgePath(d, nodeMap, colMap))
        .attr('fill', 'none').attr('stroke', 'rgba(251,191,36,0.22)').attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '6,3').attr('marker-end', 'url(#arr-col)');
    }

    // === NODES ===
    const ne = svgGroup.append('g').selectAll('g').data(tableNodes).enter().append('g')
      .attr('class', 'node-rect-group').attr('transform', d => `translate(${d.x},${d.y})`).style('cursor', 'pointer')
      .on('click', (ev, d) => { ev.stopPropagation(); hlLineage(d, tableNodes, tableLinks, ne, le, cle, columnLinks, colMap, exprMap); showDetail(d, colMap, columnLinks, exprMap); });

    ne.append('rect').attr('class', 'node-rect').attr('width', NODE_W).attr('height', d => d._h).attr('rx', 8)
      .attr('fill', d => getNodeColor(d).bg.replace('0.08', '0.25'))
      .attr('stroke', d => getNodeColor(d).border).attr('stroke-width', 1.5);
    ne.append('rect').attr('width', 4).attr('height', d => d._h).attr('rx', 2).attr('fill', d => getNodeColor(d).fill);
    ne.append('text').attr('x', 16).attr('y', HEADER_H / 2).attr('dominant-baseline', 'central').attr('font-size', '14px')
      .text(d => NODE_TYPE_ICONS[d.type] || '⊞');
    ne.append('text').attr('class', 'node-name-label').attr('x', 34).attr('y', HEADER_H / 2).attr('dominant-baseline', 'central')
      .attr('font-family', "'JetBrains Mono',monospace").attr('font-size', '11px').attr('fill', '#E5E7EB').attr('font-weight', '600')
      .text(d => d.name.length > 22 ? d.name.slice(0, 21) + '…' : d.name).append('title').text(d => d.id);
    ne.filter(d => d.source_file).append('text').attr('x', NODE_W - 8).attr('y', HEADER_H / 2)
      .attr('dominant-baseline', 'central').attr('text-anchor', 'end').attr('font-size', '8px').attr('fill', 'rgba(255,255,255,0.2)')
      .text(d => d.source_file);

    // === COLUMN ROWS ===
    if (showColumns) {
      ne.each(function (d) {
        const cols = colMap[d.id]; if (!cols || !cols.length) return;
        const g = d3.select(this);
        const te = exprMap[d.id] || {};
        g.append('line').attr('x1', 10).attr('x2', NODE_W - 10).attr('y1', HEADER_H - 1).attr('y2', HEADER_H - 1)
          .attr('stroke', getNodeColor(d).border).attr('stroke-width', 0.5);
        cols.forEach((c, ci) => {
          const ry = HEADER_H + ci * COL_ROW_H;
          const expr = te[c];
          const pass = !expr || expr.toLowerCase() === c.toLowerCase();
          if (ci % 2 === 0) g.append('rect').attr('x', 5).attr('y', ry).attr('width', NODE_W - 10).attr('height', COL_ROW_H).attr('rx', 3).attr('fill', 'rgba(255,255,255,0.02)');
          g.append('circle').attr('class', 'col-dot').attr('cx', 18).attr('cy', ry + 13).attr('r', 3).attr('fill', pass ? 'rgba(167,139,250,0.5)' : 'rgba(251,191,36,0.7)');
          g.append('text').attr('class', 'col-label').attr('x', 28).attr('y', ry + 13).attr('dominant-baseline', 'central')
            .attr('font-family', "'JetBrains Mono',monospace").attr('font-size', '9.5px')
            .attr('fill', pass ? 'rgba(255,255,255,0.50)' : 'rgba(251,191,36,0.8)')
            .text(c.length > 24 ? c.slice(0, 23) + '…' : c).append('title').text(c);
          if (!pass && expr) {
            const de = expr.length > 28 ? expr.slice(0, 27) + '…' : expr;
            g.append('text').attr('class', 'col-expr').attr('x', 28).attr('y', ry + 27).attr('dominant-baseline', 'central')
              .attr('font-family', "'JetBrains Mono',monospace").attr('font-size', '7.5px').attr('fill', 'rgba(255,255,255,0.22)')
              .text('ƒ ' + de).append('title').text(expr);
          }
        });
      });
    }

    graphSvg._ne = ne; graphSvg._le = le; graphSvg._cle = cle;
    graphSvg._nodes = tableNodes; graphSvg._links = tableLinks; graphSvg._colLinks = columnLinks;
    graphSvg._nodeMap = nodeMap; graphSvg._colMap = colMap; graphSvg._exprMap = exprMap;
    setTimeout(fitToView, 100);
  }

  /* ================================================================
     EDGE PATHS
     ================================================================ */
  function edgePath(src, tgt, sh, th) {
    const sx = src.x + NODE_W, sy = src.y + (sh || HEADER_H) / 2, tx = tgt.x, ty = tgt.y + (th || HEADER_H) / 2;
    if (tx > sx) { const mx = (sx + tx) / 2; return `M${sx},${sy}C${mx},${sy} ${mx},${ty} ${tx},${ty}`; }
    const o = 40, top = Math.min(sy, ty) - o;
    return `M${sx},${sy}C${sx + o},${sy} ${sx + o},${top} ${(sx + tx) / 2},${top}S${tx - o},${ty} ${tx},${ty}`;
  }
  function colEdgePath(lk, nm, cm) {
    const st = lk.source_table, sc = lk.source_column, tt = lk.target_table, tc = lk.target_column;
    if (!st || !tt) return '';
    const sn = nm[st], tn = nm[tt]; if (!sn || !tn) return '';
    const srcCols = cm[st] || [], tgtCols = cm[tt] || [];
    const si = srcCols.indexOf(sc), ti = tgtCols.indexOf(tc);
    if (si < 0 || ti < 0) return '';
    const sx = sn.x + NODE_W, sy = sn.y + HEADER_H + si * COL_ROW_H + 13;
    const tx = tn.x, ty = tn.y + HEADER_H + ti * COL_ROW_H + 13;
    if (tx > sx) { const mx = (sx + tx) / 2; return `M${sx},${sy}C${mx},${sy} ${mx},${ty} ${tx},${ty}`; }
    const o = 30, top = Math.min(sy, ty) - o;
    return `M${sx},${sy}C${sx + o},${sy} ${sx + o},${top} ${(sx + tx) / 2},${top}S${tx - o},${ty} ${tx},${ty}`;
  }

  /* ================================================================
     HIGHLIGHT LINEAGE
     ================================================================ */
  function hlLineage(node, nodes, links, ne, le, cle, colLinks, colMap, exprMap) {
    currentHighlight = node.id;
    const conn = new Set([node.id]), cIdx = new Set();
    [node.id].concat([]).forEach(() => { }); // placeholder
    // BFS up
    const uq = [node.id]; while (uq.length) { const cur = uq.shift(); links.forEach((l, i) => { const s = l.source, t = l.target; if (t === cur && !conn.has(s)) { conn.add(s); cIdx.add(i); uq.push(s); } }); }
    // BFS down
    const dq = [node.id]; while (dq.length) { const cur = dq.shift(); links.forEach((l, i) => { const s = l.source, t = l.target; if (s === cur && !conn.has(t)) { conn.add(t); cIdx.add(i); dq.push(t); } }); }
    links.forEach((l, i) => { if (conn.has(l.source) && conn.has(l.target)) cIdx.add(i); });

    ne.each(function (d) {
      const el = d3.select(this), c = conn.has(d.id), s = d.id === node.id;
      el.select('.node-rect').attr('stroke-width', s ? 3 : 1.5).attr('stroke', s ? '#60A5FA' : c ? getNodeColor(d).fill : 'rgba(255,255,255,0.04)').attr('fill-opacity', c ? 1 : 0.2);
      el.select('.node-name-label').attr('fill', c ? '#F3F4F6' : 'rgba(255,255,255,0.15)');
      el.selectAll('.col-label').attr('fill', c ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.08)');
      el.selectAll('.col-dot').attr('fill', c ? 'rgba(167,139,250,0.7)' : 'rgba(167,139,250,0.1)');
      el.selectAll('.col-expr').attr('fill', c ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.05)');
      el.style('opacity', c ? 1 : 0.25);
    });
    le.attr('stroke', (d, i) => cIdx.has(i) ? '#60A5FA' : 'rgba(255,255,255,0.04)')
      .attr('stroke-width', (d, i) => cIdx.has(i) ? 3 : 1)
      .attr('marker-end', (d, i) => cIdx.has(i) ? 'url(#arr-hl)' : 'url(#arr)')
      .attr('opacity', (d, i) => cIdx.has(i) ? 1 : 0.15);
    if (cle) {
      cle.each(function (d) {
        const inv = conn.has(d.source_table) && conn.has(d.target_table);
        d3.select(this).attr('stroke', inv ? 'rgba(251,191,36,0.55)' : 'rgba(251,191,36,0.03)')
          .attr('stroke-width', inv ? 2 : 0.5).attr('opacity', inv ? 1 : 0.1)
          .attr('marker-end', inv ? 'url(#arr-col-hl)' : 'url(#arr-col)');
      });
    }
  }

  function clearHighlight() {
    currentHighlight = null;
    const ne = graphSvg._ne, le = graphSvg._le, cle = graphSvg._cle;
    if (!ne) return;
    ne.each(function (d) {
      const el = d3.select(this);
      el.select('.node-rect').attr('stroke-width', 1.5).attr('stroke', getNodeColor(d).border).attr('fill-opacity', 1);
      el.select('.node-name-label').attr('fill', '#E5E7EB');
      el.selectAll('.col-label').attr('fill', 'rgba(255,255,255,0.50)');
      el.selectAll('.col-dot').attr('fill', 'rgba(167,139,250,0.5)');
      el.selectAll('.col-expr').attr('fill', 'rgba(255,255,255,0.22)');
      el.style('opacity', 1);
    });
    le.attr('stroke', 'rgba(255,255,255,0.12)').attr('stroke-width', 2).attr('marker-end', 'url(#arr)').attr('opacity', 1);
    if (cle) cle.attr('stroke', 'rgba(251,191,36,0.22)').attr('stroke-width', 1.5).attr('opacity', 1).attr('marker-end', 'url(#arr-col)');
    detailSection.style.display = 'none';
  }

  /* ================================================================
     DETAIL PANEL — with Column Flow Diagram
     ================================================================ */
  function showDetail(node, colMap, colLinks, exprMap) {
    detailSection.style.display = 'block';
    const tlinks = graphData.links.filter(l => l.type === 'table_to_table');
    const upstream = tlinks.filter(l => l.target === node.id && l.source !== node.id).map(l => l.source);
    const downstream = tlinks.filter(l => l.source === node.id && l.target !== node.id).map(l => l.target);
    const colors = getNodeColor(node);
    const cols = colMap[node.id] || [];
    const te = exprMap[node.id] || {};
    const inEdges = colLinks.filter(l => l.target_table === node.id);
    const outEdges = colLinks.filter(l => l.source_table === node.id);

    let html = `<div class="detail-name">${node.id}</div>`;
    html += `<div class="detail-row"><span class="detail-key">Type</span><span class="detail-value">${node.type}</span></div>`;
    html += `<div class="detail-row"><span class="detail-key">Layer</span><span class="detail-value" style="color:${colors.fill}">${colors.label}</span></div>`;
    if (node.source_file) html += `<div class="detail-row"><span class="detail-key">File</span><span class="detail-value">${node.source_file}</span></div>`;

    // === COLUMN FLOW DIAGRAM ===
    if (cols.length > 0) {
      html += `<div class="lineage-list"><h4>📋 Column Dependencies (${cols.length})</h4>`;
      html += `<div class="col-flow-container">`;
      cols.forEach(c => {
        const expr = te[c];
        const pass = !expr || expr.toLowerCase() === c.toLowerCase();
        const sources = inEdges.filter(e => e.target_column === c);
        const targets = outEdges.filter(e => e.source_column === c);
        const dotColor = pass ? '#A78BFA' : '#FBBF24';

        html += `<div class="col-flow-row">`;

        // LEFT: Source columns
        html += `<div class="col-flow-sources">`;
        if (sources.length) {
          sources.forEach(s => {
            html += `<div class="col-flow-src-item">`;
            html += `<span class="col-flow-table">${shortName(s.source_table)}</span>`;
            html += `<span class="col-flow-col">.${s.source_column}</span>`;
            html += `</div>`;
          });
        } else {
          html += `<div class="col-flow-src-item"><span class="col-flow-no-src">—</span></div>`;
        }
        html += `</div>`;

        // MIDDLE: Arrow + transformation
        html += `<div class="col-flow-transform">`;
        if (!pass && expr) {
          html += `<div class="col-flow-arrow">→</div>`;
          html += `<div class="col-flow-expr" title="${esc(expr)}">ƒ ${esc(expr.length > 20 ? expr.slice(0, 19) + '…' : expr)}</div>`;
          html += `<div class="col-flow-arrow">→</div>`;
        } else {
          html += `<div class="col-flow-arrow col-flow-pass">→→</div>`;
        }
        html += `</div>`;

        // RIGHT: Output column
        html += `<div class="col-flow-output">`;
        html += `<span class="col-flow-dot" style="background:${dotColor}"></span>`;
        html += `<span class="col-flow-out-name">${c}</span>`;
        html += `</div>`;

        // BOTTOM-RIGHT: targets
        if (targets.length) {
          html += `<div class="col-flow-targets">`;
          targets.forEach(t => {
            html += `<span class="col-flow-tgt">→ ${shortName(t.target_table)}.${t.target_column}</span>`;
          });
          html += `</div>`;
        }

        html += `</div>`; // .col-flow-row
      });
      html += `</div></div>`;
    }

    // Table deps
    if (upstream.length) {
      html += `<div class="lineage-list"><h4>⬆ Depends On (${upstream.length})</h4>`;
      upstream.forEach(id => { html += `<div class="lineage-item" data-node-id="${id}">${id}</div>`; });
      html += `</div>`;
    }
    if (downstream.length) {
      html += `<div class="lineage-list"><h4>⬇ Used By (${downstream.length})</h4>`;
      downstream.forEach(id => { html += `<div class="lineage-item" data-node-id="${id}">${id}</div>`; });
      html += `</div>`;
    }

    nodeDetails.innerHTML = html;
    nodeDetails.querySelectorAll('.lineage-item[data-node-id]').forEach(el => {
      el.addEventListener('click', () => {
        const t = graphSvg._nodes.find(n => n.id === el.dataset.nodeId);
        if (t) { hlLineage(t, graphSvg._nodes, graphSvg._links, graphSvg._ne, graphSvg._le, graphSvg._cle, graphSvg._colLinks, graphSvg._colMap, graphSvg._exprMap); showDetail(t, graphSvg._colMap, graphSvg._colLinks, graphSvg._exprMap); panTo(t); }
      });
    });
  }

  function shortName(id) { const d = id.lastIndexOf('.'); return d >= 0 ? id.slice(d + 1) : id; }
  function panTo(n) {
    const t = d3.zoomTransform(graphSvg);
    d3.select(graphSvg).transition().duration(500).call(zoom.transform,
      d3.zoomIdentity.translate(-n.x * t.k + graphSvg.parentElement.clientWidth / 2 - NODE_W / 2, -n.y * t.k + graphSvg.parentElement.clientHeight / 2).scale(t.k));
  }

  /* ================================================================
     CONTROLS
     ================================================================ */
  function fitToView() {
    const ns = graphSvg._nodes; if (!ns || !ns.length) return;
    const w = graphSvg.parentElement.clientWidth, h = graphSvg.parentElement.clientHeight, p = 80;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    ns.forEach(n => { x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x + NODE_W); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y + (n._h || HEADER_H)); });
    const s = Math.min(w / (x1 - x0 + p * 2), h / (y1 - y0 + p * 2), 1.2);
    d3.select(graphSvg).transition().duration(600).call(zoom.transform,
      d3.zoomIdentity.translate(w / 2, h / 2).scale(s).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
  }

  function handleSearch() {
    const q = searchInput.value.trim().toLowerCase();
    if (!graphSvg._ne) return;
    if (!q) { clearHighlight(); return; }
    const m = new Set();
    graphSvg._nodes.forEach(n => { if (n.name.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)) m.add(n.id); });
    const cm = graphSvg._colMap || {};
    Object.entries(cm).forEach(([tid, cols]) => { cols.forEach(c => { if (c.toLowerCase().includes(q)) m.add(tid); }); });
    graphSvg._ne.each(function (d) {
      const el = d3.select(this), ok = m.has(d.id);
      el.style('opacity', !m.size || ok ? 1 : 0.15);
      el.select('.node-rect').attr('stroke', ok ? '#60A5FA' : getNodeColor(d).border).attr('stroke-width', ok ? 3 : 1.5);
    });
    if (m.size) { const f = graphSvg._nodes.find(n => m.has(n.id)); if (f) panTo(f); }
  }

  /* ================================================================
     EXPORT
     ================================================================ */
  function exportPNG() {
    if (!graphSvg) return;
    const s = new XMLSerializer().serializeToString(graphSvg);
    const u = URL.createObjectURL(new Blob([s], { type: 'image/svg+xml;charset=utf-8' }));
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = graphSvg.clientWidth * 2; c.height = graphSvg.clientHeight * 2;
      const ctx = c.getContext('2d'); ctx.fillStyle = '#0B0F1A'; ctx.fillRect(0, 0, c.width, c.height); ctx.scale(2, 2); ctx.drawImage(img, 0, 0);
      c.toBlob(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'sql-lineage.png'; a.click(); });
      URL.revokeObjectURL(u);
    };
    img.src = u; showToast('Exported as PNG', 'success');
  }
  function exportJSON() {
    if (!graphData) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' }));
    a.download = 'sql-lineage.json'; a.click(); URL.revokeObjectURL(a.href); showToast('Exported as JSON', 'success');
  }

  /* ================================================================
     TOAST / UTIL
     ================================================================ */
  function showToast(msg, type = 'info') {
    const c = document.getElementById('toast-container'), t = document.createElement('div');
    t.className = `toast ${type}`; t.textContent = msg; c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateY(12px)'; t.style.transition = 'all 300ms'; setTimeout(() => t.remove(), 300); }, 3500);
  }
  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  init();
})();
