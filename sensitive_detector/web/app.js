export function splitLines(text) {
  return text.split(/\r?\n/u).map(line => line.trim()).filter(Boolean);
}

export function validateLines(texts) {
  if (texts.length < 1 || texts.length > 100) throw new Error('每批需要 1–100 条非空文本。');
  if (texts.some(text => Array.from(text).length > 8000)) throw new Error('每条文本不能超过 8000 字符。');
  if (texts.reduce((sum, text) => sum + Array.from(text).length, 0) > 32000) throw new Error('每批总长不能超过 32000 字符。');
  return texts;
}

export function badgeClass(label) {
  return label === 1 ? 'warn' : label === 2 ? 'quote' : 'neutral';
}

async function initialize() {
  const el = id => document.getElementById(id);
  let result = null;
  let startupRules;
  let backend = 'rules';
  let busy = false;
  const message = text => { el('message').textContent = text; };
  function invalidate() {
    result = null;
    el('export').disabled = true;
    el('results').replaceChildren();
    for (const key of ['total', 'review', 'quoted', 'unmatched']) el(key).textContent = '0';
  }
  function counter() { el('counter').textContent = `${Array.from(el('input').value).length} 字符`; }
  function add(parent, tag, text, className = '') {
    const node = document.createElement(tag);
    node.textContent = text;
    node.className = className;
    parent.append(node);
    return node;
  }
  function render(data) {
    el('results').replaceChildren();
    for (const [index, row] of data.results.entries()) {
      const item = add(el('results'), 'article', '', 'result-item');
      const head = add(item, 'div', '', 'result-head');
      add(head, 'span', `TEXT ${String(index + 1).padStart(2, '0')}`, 'item-id');
      add(head, 'span', row.status, `badge ${badgeClass(row.label)}`);
      add(item, 'p', row.text, 'result-text');
      for (const finding of row.findings) {
        const detail = add(item, 'div', finding.reason, 'finding');
        add(detail, 'strong', `参考：${finding.reference} · 规则 ${finding.rule_id}`);
      }
      if (!row.findings.length) add(item, 'div', '当前规则未命中；不代表内容一定合规。', 'finding');
    }
    for (const key of ['total', 'review', 'quoted', 'unmatched']) el(key).textContent = String(data.summary[key]);
  }
  const demo = '这是一条示例敏感词测试。\n谦受益满招害。\n谦受益，满招损。\n今天的天气适合散步。';
  el('demo').addEventListener('click', () => { if (busy) return; invalidate(); el('input').value = demo; counter(); message(''); });
  el('clear').addEventListener('click', () => { if (busy) return; invalidate(); el('input').value = ''; el('file').value = ''; counter(); message('已清空本次文本与结果。'); });
  el('input').addEventListener('input', () => { invalidate(); counter(); });
  el('rules').addEventListener('input', invalidate);
  el('reset-rules').addEventListener('click', () => { if (busy || !startupRules) return; el('rules').value = JSON.stringify(startupRules, null, 2); invalidate(); message('已恢复启动词库。'); });
  el('file').addEventListener('change', async () => {
    if (busy) return;
    try {
      const file = el('file').files[0];
      if (!file) return;
      if (file.size > 1024 * 1024) throw new Error('TXT 文件不能超过 1 MiB。');
      const text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
      if (busy) throw new Error('检测中，请稍后重新导入。');
      validateLines(splitLines(text));
      el('input').value = text;
      invalidate(); counter(); message('已导入 TXT，点击开始检测。');
    } catch (error) { message(error.message); }
    finally { el('file').value = ''; }
  });
  el('analyze').addEventListener('click', async () => {
    if (busy) return;
    try {
      const texts = validateLines(splitLines(el('input').value));
      const payload = { texts };
      if (backend === 'rules') payload.rules = JSON.parse(el('rules').value);
      busy = true;
      el('analyze').disabled = true;
      el('input').readOnly = true;
      el('rules').readOnly = true;
      el('file').disabled = true;
      invalidate(); message('正在本机检测…');
      const response = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '检测失败');
      result = data;
      render(data);
      el('export').disabled = false;
      message('');
    } catch (error) { invalidate(); message(error.message || '本地服务连接失败'); }
    finally {
      busy = false;
      el('analyze').disabled = false;
      el('input').readOnly = false;
      el('rules').readOnly = backend === 'semantic';
      el('file').disabled = false;
    }
  });
  el('export').addEventListener('click', () => {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url; link.download = 'review-results.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  try {
    const responses = await Promise.all([fetch('/api/health'), fetch('/api/rules')]);
    if (responses.some(response => !response.ok)) throw new Error('本地服务初始化失败');
    const [health, rules] = await Promise.all(responses.map(response => response.json()));
    backend = health.backend; startupRules = rules;
    el('rules').value = JSON.stringify(rules, null, 2);
    el('rules').readOnly = backend === 'semantic';
    el('connection').textContent = backend === 'rules' ? '本地连接正常 · 规则模式' : '本地连接正常 · 语义模式';
    if (backend === 'semantic') message('语义模式使用启动时的词库，修改词库后需重启服务。');
  } catch (error) { el('connection').textContent = '本地服务未连接'; el('analyze').disabled = true; message(error.message); }
}

if (typeof document !== 'undefined') initialize();
