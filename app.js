/* Hyper Tech Widget — HyDeck site */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Where each theme pack is sold. Paste your Gumroad product links here.
  // While a link is empty the button stays on "Coming soon". Only https Gumroad addresses are accepted.
  const SHOP = { midas: 'https://mrvenkham.gumroad.com/l/hydeck-midas', gym: 'https://mrvenkham.gumroad.com/l/hydeck-gym' };
  const isGumroad = (u) => {
    try {
      const x = new URL(u);
      const h = x.hostname.toLowerCase();
      return x.protocol === 'https:' && (h === 'gumroad.com' || h.endsWith('.gumroad.com') || h === 'gum.co');
    } catch { return false; }
  };
  for (const a of $$('a[data-buy]')) {
    const url = (SHOP[a.dataset.buy] || '').trim();
    if (!isGumroad(url)) continue;
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = 'Buy on Gumroad';
    a.classList.remove('disabled');
    a.removeAttribute('aria-disabled');
  }

  // the looks that ship free, and the paid pack (locked)
  const FREE = ['cyan', 'red', 'hifi'];
  const NAMES = { cyan: 'CYAN LCD', red: 'RED MIXER', hifi: 'HI-FI', midas: 'MIDAS', gym: 'GYM' };
  const PACKS = {
    midas: { img: 'media/midas.png', gold: true, link: '#midas', label: 'How MIDAS works' },
    gym: { img: 'media/gym-applause.png', gold: false, link: '#gym', label: 'How GYM works' },
  };
  const state = { look: 'cyan', roulette: false, paused: false };

  const hero = $('#heroVideo');
  const lockCard = $('#lockCard');
  const hint = $('#hint');

  // ───────── the look in the phone (real recordings of the real app) ─────────
  function playSafe(v) {
    if (!v || state.paused) return;
    const p = v.play();
    if (p && p.catch) p.catch(() => { /* the browser blocked autoplay: the poster stays visible */ });
  }

  function setLook(id, { quiet = false } = {}) {
    if (!NAMES[id]) return;
    state.look = id;
    $$('.pick').forEach(b => {
      const on = b.dataset.look === id;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
    });
    if (id === 'midas' || id === 'gym') {
      const pack = PACKS[id];
      lockCard.dataset.pack = id;
      $('img', lockCard).src = pack.img;
      $('strong', lockCard).textContent = NAMES[id];
      const more = $('a', lockCard);
      more.href = pack.link;
      more.textContent = pack.label;
      lockCard.hidden = false;
      hero.pause();
      if (!quiet) hint.textContent = `${NAMES[id]} is a paid theme pack: it is locked until you enter a code.`;
      return;
    }
    lockCard.hidden = true;
    document.body.dataset.theme = id; // the page itself wears the look too
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = getComputedStyle(document.body).getPropertyValue('--bg').trim() || '#031319';
    hero.setAttribute('poster', `media/${id}.png`);
    hero.setAttribute('aria-label', `Recording of the HyDeck app showing the ${NAMES[id]} look`);
    hero.src = `media/${id}.mp4`;
    hero.load();
    playSafe(hero);
    if (!quiet) hint.textContent = `${NAMES[id]} is free and built into the app.`;
  }

  $$('.pick').forEach(b => b.addEventListener('click', () => setLook(b.dataset.look)));
  $$('.card[data-go]').forEach(c => {
    const go = () => { setLook(c.dataset.go); $('#try').scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' }); };
    c.addEventListener('click', go);
    c.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  });

  // roulette: the phone changes look by itself
  let rouletteTimer = null;
  $('#roulette').addEventListener('change', e => {
    state.roulette = e.target.checked;
    clearInterval(rouletteTimer);
    if (state.roulette) {
      hint.textContent = '🎲 On: a new look every few seconds, like a new song.';
      rouletteTimer = setInterval(() => {
        const options = FREE.filter(f => f !== state.look);
        setLook(options[Math.floor(Math.random() * options.length)], { quiet: true });
        hint.textContent = `🎲 Roulette picked ${NAMES[state.look]}.`;
      }, 6000);
    } else {
      hint.textContent = 'Roulette is off.';
    }
  });

  // pause every video (for anyone who prefers still pictures)
  $('#pauseAll').addEventListener('click', e => {
    state.paused = !state.paused;
    e.currentTarget.setAttribute('aria-pressed', String(state.paused));
    e.currentTarget.textContent = state.paused ? '▶ Play videos' : '⏸ Pause videos';
    $$('video').forEach(v => (state.paused ? v.pause() : (v === hero && state.look === 'midas' ? null : playSafe(v))));
  });

  // videos further down only play while they are on screen
  const lazyVideos = $$('#volVideo, #midasVideo, #gymVideo');
  if ('IntersectionObserver' in window) {
    const vio = new IntersectionObserver(es => es.forEach(en => {
      const v = en.target;
      if (en.isIntersecting) { if (v.preload === 'none') v.preload = 'auto'; playSafe(v); } else v.pause();
    }), { threshold: 0.25 });
    lazyVideos.forEach(v => vio.observe(v));
  } else {
    lazyVideos.forEach(v => playSafe(v));
  }

  // ───────── the word that changes ─────────
  const words = ['new look', 'new mood', 'new outfit', 'new vibe'];
  let wi = 0;
  const swap = $('#swapWord');
  if (!reduceMotion) setInterval(() => {
    wi = (wi + 1) % words.length;
    swap.animate([{ opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(-8px)' }], { duration: 220 }).onfinish = () => {
      swap.textContent = words[wi];
      swap.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 260 });
    };
  }, 2600);

  // ───────── roulette reel ─────────
  const reelIn = $('#reelIn');
  reelIn.innerHTML = Array.from({ length: 5 * FREE.length }, (_, i) => `<div>${NAMES[FREE[i % FREE.length]]}</div>`).join('');
  let reelAt = 0;
  $('#spin').addEventListener('click', () => {
    const target = Math.floor(Math.random() * FREE.length);
    reelIn.style.transition = 'none';
    reelIn.style.transform = `translateY(${-reelAt * 64}px)`;
    reelIn.offsetHeight; // restart the transition
    reelAt = 3 * FREE.length + target;
    reelIn.style.transition = reduceMotion ? 'none' : '';
    reelIn.style.transform = `translateY(${-reelAt * 64}px)`;
    setTimeout(() => {
      setLook(FREE[target]);
      reelAt = target;
      reelIn.style.transition = 'none';
      reelIn.style.transform = `translateY(${-reelAt * 64}px)`;
    }, reduceMotion ? 0 : 2300);
  });

  // ───────── match the vibe (a simplified version of the idea) ─────────
  const LEX = {
    rock: ['rock', 'metal', 'metallica', 'nirvana', 'guitar', 'punk', 'ac/dc', 'acdc', 'linkin', 'queen', 'sandman', 'thunder', 'riff'],
    sad: ['sad', 'cry', 'tears', 'broken', 'alone', 'heartbreak', 'goodbye', 'lonely', 'miss you', 'rain'],
    romantic: ['love', 'heart', 'kiss', 'baby', 'romance', 'valentine', 'forever', 'darling'],
    chill: ['chill', 'lofi', 'lo-fi', 'relax', 'acoustic', 'calm', 'sleep', 'coffee', 'jazz', 'study', 'ambient'],
    party: ['party', 'dance', 'club', 'remix', 'dj', 'edm', 'disco', 'tonight'],
    energetic: ['workout', 'gym', 'fast', 'run', 'energy', 'hype', 'beast', 'phonk', 'adrenaline'],
    dark: ['dark', 'shadow', 'horror', 'evil', 'midnight', 'black', 'dead', 'demon'],
    epic: ['epic', 'hero', 'battle', 'soundtrack', 'orchestra', 'victory', 'champion', 'legend', 'anthem'],
    retro: ['retro', '80s', '90s', 'vintage', 'synth', 'oldies', 'arcade', 'pixel'],
    hopeful: ['hope', 'dream', 'sunrise', 'light', 'believe', 'better', 'sun', 'dawn'],
  };
  const LABEL = { rock: '⚡ Rock', sad: '💧 Sad', romantic: '❤ Romantic', chill: '🌿 Chill', party: '🎉 Party', energetic: '🔥 Energetic', dark: '🌑 Dark', epic: '🏔 Epic', retro: '🕹 Retro', hopeful: '☀ Hopeful' };
  const MOOD_LOOK = { rock: 'red', energetic: 'red', party: 'red', dark: 'cyan', chill: 'cyan', retro: 'cyan', sad: 'hifi', romantic: 'hifi', hopeful: 'hifi', epic: 'midas' };
  const vibeIn = $('#vibeIn'), vibeOut = $('#vibeOut');
  function detectMoods(text) {
    const t = text.toLowerCase();
    return Object.entries(LEX)
      .map(([m, ws]) => [m, ws.reduce((s, w) => s + (new RegExp(`(^|[^a-z0-9])${w.replace(/[/]/g, '\\/')}`).test(t) ? 1 : 0), 0)])
      .filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([m]) => m);
  }
  vibeIn.addEventListener('input', () => {
    const text = vibeIn.value.trim();
    if (!text) { vibeOut.innerHTML = '<span class="muted">Waiting for a song…</span>'; return; }
    const moods = detectMoods(text);
    if (!moods.length) { vibeOut.innerHTML = '<span class="muted">No clear vibe from the words, so HyDeck would keep its usual look.</span>'; return; }
    const pick = MOOD_LOOK[moods[0]];
    const paid = pick === 'midas';
    vibeOut.innerHTML = moods.map(m => `<span class="tag">${LABEL[m]}</span>`).join('') +
      `<button class="tag go${paid ? ' gold' : ''}" type="button" data-look="${pick}">${paid ? '🔒 ' : '→ '}${NAMES[pick]}${paid ? ' (paid pack)' : ''}</button>`;
  });
  vibeOut.addEventListener('click', e => {
    const b = e.target.closest('.go');
    if (b) { setLook(b.dataset.look); $('#try').scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' }); }
  });

  // ───────── download card, from the same file the app reads ─────────
  async function loadRelease() {
    const meta = $('#dlMeta'), ver = $('#dlVer'), btn = $('#dlBtn'), sha = $('#dlSha'), copy = $('#copySha'), notes = $('#dlNotes');
    try {
      const r = await fetch('hydeck/latest.json', { cache: 'no-store' });
      if (!r.ok) throw new Error(r.status);
      const j = await r.json();
      if (!j || typeof j.version !== 'string' || typeof j.apk !== 'string' || !/^[0-9a-f]{64}$/i.test(j.sha256 || '')) throw new Error('bad file');
      ver.textContent = `v${j.version}`;
      meta.textContent = `Android 7+ · ${j.size ? (j.size / 1048576).toFixed(1) + ' MB · ' : ''}build ${j.build}`;
      btn.href = j.apk;
      btn.textContent = `Download HyDeck ${j.version}`;
      btn.classList.remove('disabled');
      btn.removeAttribute('aria-disabled');
      sha.textContent = j.sha256.toLowerCase();
      copy.disabled = false;
      copy.onclick = async () => { try { await navigator.clipboard.writeText(sha.textContent); copy.textContent = 'Copied ✓'; setTimeout(() => (copy.textContent = 'Copy'), 1500); } catch (_) { /* ignore */ } };
      notes.textContent = j.notes || '';
    } catch (_) {
      ver.textContent = '';
      meta.textContent = 'The first public version is coming soon. Check back here.';
      btn.textContent = 'Coming soon';
    }
  }

  // ───────── for people on a computer: a code and a link to send to their phone ─────────
  function setupShare() {
    const url = location.href.split('#')[0] + '#download';
    const mail = $('#mailLink');
    mail.href = `mailto:?subject=${encodeURIComponent('HyDeck for my Android phone')}&body=${encodeURIComponent('Open this on your phone to get HyDeck:\n' + url)}`;
    const copy = $('#copyLink');
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(url); copy.textContent = 'Link copied ✓'; }
      catch (_) { copy.textContent = url; }
      setTimeout(() => (copy.textContent = 'Copy the link'), 2200);
    });
    // the QR code comes from a small, well-known library; if it can't load, the link buttons still work
    const box = $('#qr');
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
    s.onload = () => { try { new window.QRCode(box, { text: url, width: 136, height: 136, correctLevel: window.QRCode.CorrectLevel.M }); } catch (_) { box.hidden = true; } };
    s.onerror = () => { box.hidden = true; };
    document.head.appendChild(s);
  }

  // ───────── reveal on scroll ─────────
  function reveal() {
    const items = $$('.head, .card, .panel, .step, .flow li, .dl-card, .pc-box, .faq details, .shots figure, .sync, .midas-grid > *, .promise');
    if (!('IntersectionObserver' in window) || reduceMotion) return;
    items.forEach(el => el.classList.add('reveal'));
    const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } }), { threshold: 0.1 });
    items.forEach(el => io.observe(el));
    // never leave anything hidden if the observer is slow
    setTimeout(() => items.forEach(el => { if (el.getBoundingClientRect().top < innerHeight) el.classList.add('in'); }), 1200);
  }

  $('#year').textContent = new Date().getFullYear();
  playSafe(hero);
  loadRelease();
  setupShare();
  reveal();
})();
