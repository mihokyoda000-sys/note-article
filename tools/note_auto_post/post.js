const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(question, (ans) => { rl.close(); resolve(ans); }));
}

function parseArticle(mdText) {
  const fmMatch = mdText.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!fmMatch) {
    throw new Error('frontmatterが見つかりません。ファイル先頭を "---\\ntitle: ...\\ntags: [...]\\n---" の形式にしてください。');
  }
  const fm = fmMatch[1];
  const body = fmMatch[2];
  const titleMatch = fm.match(/title:\s*"(.*)"/) || fm.match(/title:\s*(.*)/);
  const tagsMatch = fm.match(/tags:\s*\[(.*)\]/);
  const title = titleMatch ? titleMatch[1].trim() : '';
  const tags = tagsMatch
    ? tagsMatch[1].split(',').map((t) => t.trim().replace(/^"|"$/g, '')).filter(Boolean)
    : [];
  return { title, tags, body };
}

function parseBody(md) {
  const blocks = md.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const result = [];
  for (const b of blocks) {
    if (b === '---') {
      result.push({ type: 'paywall-marker' });
    } else if (b.startsWith('### ')) {
      result.push({ type: 'h3', raw: b.slice(4) });
    } else if (b.startsWith('## ')) {
      result.push({ type: 'h2', raw: b.slice(3) });
    } else if (b.startsWith('- ')) {
      const items = b.split('\n').map((l) => l.replace(/^- /, ''));
      result.push({ type: 'ul', items });
    } else if (/^\*\*\(.*\)\*\*$/.test(b)) {
      result.push({ type: 'paywall-marker' });
    } else {
      result.push({ type: 'p', raw: b });
    }
  }
  return result;
}

function splitBold(raw) {
  return raw
    .split(/(\*\*[^*]+\*\*)/g)
    .filter((s) => s.length)
    .map((p) => (p.startsWith('**') && p.endsWith('**'))
      ? { bold: true, text: p.slice(2, -2) }
      : { bold: false, text: p });
}

async function typeSegments(page, segments) {
  for (const seg of segments) {
    if (seg.bold) {
      await page.keyboard.press('Control+b');
      await page.keyboard.type(seg.text, { delay: 15 });
      await page.keyboard.press('Control+b');
    } else {
      await page.keyboard.type(seg.text, { delay: 15 });
    }
  }
}

async function typeBlock(page, block) {
  switch (block.type) {
    case 'h2':
      await page.keyboard.type('## ', { delay: 20 });
      await typeSegments(page, splitBold(block.raw));
      await page.keyboard.press('Enter');
      break;
    case 'h3':
      await page.keyboard.type('### ', { delay: 20 });
      await typeSegments(page, splitBold(block.raw));
      await page.keyboard.press('Enter');
      break;
    case 'ul':
      for (const item of block.items) {
        await page.keyboard.type('- ', { delay: 20 });
        await typeSegments(page, splitBold(item));
        await page.keyboard.press('Enter');
      }
      await page.keyboard.press('Enter');
      break;
    case 'paywall-marker':
      await page.keyboard.type(
        '▼ここから先を「続きを読むには」設定にしてください(投稿前に手動で設定し、この行は削除してください)',
        { delay: 15 }
      );
      await page.keyboard.press('Enter');
      await page.keyboard.press('Enter');
      break;
    case 'p':
    default:
      await typeSegments(page, splitBold(block.raw));
      await page.keyboard.press('Enter');
      await page.keyboard.press('Enter');
      break;
  }
}

function normalizeSameSite(value) {
  if (!value) return 'Lax';
  const v = String(value).toLowerCase();
  if (v.includes('no_restriction') || v === 'none') return 'None';
  if (v.includes('strict')) return 'Strict';
  return 'Lax';
}

async function loadCookies(context, cookiesPath) {
  const raw = JSON.parse(fs.readFileSync(cookiesPath, 'utf-8'));
  const cookies = raw.map((c) => ({
    name: c.name,
    value: c.value,
    domain: c.domain,
    path: c.path || '/',
    expires: c.expirationDate ? Math.floor(c.expirationDate) : (typeof c.expires === 'number' ? c.expires : -1),
    httpOnly: !!c.httpOnly,
    secure: !!c.secure,
    sameSite: normalizeSameSite(c.sameSite),
  }));
  await context.addCookies(cookies);
  console.log(`${cookies.length}件のCookieを読み込みました。`);
}

async function main() {
  const args = process.argv.slice(2);
  const fileArgIdx = args.indexOf('--file');
  if (fileArgIdx === -1 || !args[fileArgIdx + 1]) {
    console.error('使い方: node post.js --file ./articles/sample.md [--cookies ./note_cookies.json]');
    process.exit(1);
  }
  const filePath = path.resolve(args[fileArgIdx + 1]);
  const mdText = fs.readFileSync(filePath, 'utf-8');
  const { title, tags, body } = parseArticle(mdText);
  const blocks = parseBody(body);

  const cookiesArgIdx = args.indexOf('--cookies');
  const cookiesPath = (cookiesArgIdx !== -1 && args[cookiesArgIdx + 1])
    ? path.resolve(args[cookiesArgIdx + 1])
    : null;

  const profileDir = path.join(__dirname, '.browser-profile');
  const context = await chromium.launchPersistentContext(profileDir, {
    headless: false,
    viewport: { width: 1280, height: 900 },
  });
  const page = context.pages()[0] || (await context.newPage());

  if (cookiesPath) {
    await loadCookies(context, cookiesPath);
  }

  await page.goto('https://note.com/notes/new', { waitUntil: 'domcontentloaded' });

  if (page.url().includes('/login')) {
    console.log('note.comにログインしていません。');
    console.log('このブラウザ内でGoogleログインを行うと、Google側にブロックされることがあります。');
    console.log('普段お使いのブラウザでnote.comにログインし、Cookieをエクスポートして');
    console.log('--cookies オプションで読み込ませることをおすすめします。');
    await ask('それでも手動でログインする場合はログイン後にEnterキーを押してください...');
    await page.goto('https://note.com/notes/new', { waitUntil: 'domcontentloaded' });
  }

  console.log('タイトル欄を探しています...');
  const titleBox = page.getByPlaceholder(/タイトル/).first();
  const foundTitle = await titleBox.count();
  if (foundTitle) {
    await titleBox.click();
  } else {
    console.log('タイトル欄を自動検出できませんでした。');
    await ask('タイトルを入力したい欄を手動でクリックしてから、Enterキーを押してください...');
  }
  await page.keyboard.type(title, { delay: 20 });

  console.log('本文欄を探しています...');
  const bodyBox = page.getByPlaceholder(/本文/).first();
  const foundBody = await bodyBox.count();
  if (foundBody) {
    await bodyBox.click();
  } else {
    await page.keyboard.press('Tab');
    console.log('本文欄を自動検出できませんでした。Tabキーで移動を試みています。');
    console.log('カーソルが本文欄にない場合は、手動でクリックしてください。');
    await ask('本文欄にカーソルがあることを確認したらEnterキーを押してください...');
  }

  console.log('本文を入力します...');
  for (const block of blocks) {
    await typeBlock(page, block);
  }

  console.log('');
  console.log('===================================');
  console.log('下書きへの自動入力が完了しました。');
  if (tags.length) {
    console.log('タグ候補(「公開に進む」画面で手動入力してください): ' + tags.join(' / '));
  }
  console.log('内容を確認し、問題なければご自身で「公開に進む」から投稿してください。');
  console.log('このスクリプトは公開ボタンを自動で押しません。');
  console.log('===================================');

  await ask('終了する場合はEnterキーを押してください(ブラウザはそのまま開いておけます)...');
  await context.close();
}

main().catch((err) => {
  console.error('エラーが発生しました:', err);
  process.exit(1);
});
