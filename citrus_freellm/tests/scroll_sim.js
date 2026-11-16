// Virtual-time model of Streamlit 1.67's chat "stick to bottom" container
// (frontend hook behind data-testid="stAppScrollToBottomContainer") plus a
// question scroll job. Used to check that the job does not fight Streamlit.
//
// Usage: node scroll_sim.js <script.js> <scenario.json>
// Prints a JSON report: final position, destination, direction reversals.
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');

const job = fs.readFileSync(process.argv[2], 'utf8');
const scenario = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

// ---------------------------------------------------------------- clock
let now = 0, serial = 0;
const tasks = new Map();  // id -> {time, fn, every}
const schedule = (fn, delay, every) => {
  const id = ++serial;
  tasks.set(id, {time: now + Math.max(0, delay), fn, every});
  return id;
};
const cancel = id => tasks.delete(id);
const frame = () => Math.ceil((now + 0.001) / 16) * 16 - now;  // next 16ms frame
const raf = fn => schedule(fn, frame());

// ---------------------------------------------------------------- layout
const space = {style: {height: '0px'}, get offsetHeight() { return parseFloat(this.style.height) || 0; }};
let contentHeight = scenario.contentHeight, targetPosition = scenario.targetPosition;
const listeners = {};
let scrollPending = false;
const trace = [];
const viewport = {
  parentElement: null, clientHeight: 600, offsetHeight: 600, _top: 0,
  get scrollHeight() { return contentHeight + space.offsetHeight; },
  get scrollTop() { return this._top; },
  set scrollTop(v) {
    const top = Math.max(0, Math.min(v, this.scrollHeight - this.clientHeight));
    if (top === this._top) return;
    this._top = top;
    trace.push([now, top]);
    if (!scrollPending) { scrollPending = true; raf(() => { scrollPending = false; emit('scroll', {}); }); }
  },
  scrollTo({top}) { this.scrollTop = top; },
  getBoundingClientRect() { return {top: 0}; },
  addEventListener(type, fn) { (listeners[type] ||= new Set()).add(fn); },
  removeEventListener(type, fn) { listeners[type]?.delete(fn); },
  dispatchEvent(event) { emit(event.type, event); return true; },
};
const emit = (type, event) => [...(listeners[type] || [])].forEach(fn => fn(event));
const wrapper = {parentElement: viewport};
const target = {parentElement: wrapper, getBoundingClientRect() { return {top: targetPosition - viewport.scrollTop}; }};
// Content grows below the question (the answer, charts) — keep scroll position.
const grow = by => { contentHeight += by; };

// ---------------------------------------------------------------- Streamlit
const st = {sticky: false, anim: true, stickyRef: false, animRef: true, c: 0, l: 0, u: 0,
            renderAt: null, effectOn: false, rafId: 0, pollE: 0, last: 0, pending: undefined, timer: 0};
const setSticky = v => { st.sticky = v; queueRender(); };
const setAnim = v => { st.anim = v; queueRender(); };
const queueRender = () => { if (st.renderAt === null) st.renderAt = schedule(render, 1); };
const bottom = () => viewport.scrollHeight - viewport.scrollTop - viewport.offsetHeight < 1;
const d = () => { st.c = now; if (!st.animRef) setSticky(false); setAnim(false); };
const f = ({timeStampLow}) => {
  if (timeStampLow <= st.c) return;
  const atBottom = bottom(), oh = viewport.offsetHeight, sh = viewport.scrollHeight;
  const g = oh !== st.l, h = sh !== st.u;
  if (g) st.l = oh;
  if (h) st.u = sh;
  if (!g && !h) { const e = st.animRef || atBottom; if (st.stickyRef !== e) setSticky(e); }
  else if (st.stickyRef) { setAnim(true); setSticky(true); }
};
const throttled = event => {
  const t = now, n = t - st.last;
  if (n > 100) { cancel(st.timer); st.pending = undefined; f(event); st.last = t; }
  else { st.pending = event; cancel(st.timer);
         st.timer = schedule(() => { if (st.pending) { f(st.pending); st.pending = undefined; st.last = now; } }, Math.max(0, 100 - n)); }
};
const Ap = (e, t) => { const n = Math.sign(t - e), r = e + Math.sqrt(Math.abs(t - e)) * n; return n > 0 ? Math.min(t, r) : Math.max(t, r); };
const jp = (e, t, r) => { let i = e; for (let k = 0; k < r; k++) i = Ap(i, t); return i; };
const animate = (start, r, o = now) => {
  cancel(st.rafId);
  st.rafId = raf(() => {
    const max = viewport.scrollHeight - viewport.offsetHeight;
    let s = jp(start, max, (now - o) / 5);
    if (Math.abs(max - s) < 1.5) s = max;
    viewport.scrollTop = s;
    if (max === s) d(); else animate(start, r + 1, o);
  });
};
const stopAnimation = () => { cancel(st.rafId); d(); };
let prevAnim = null;
function render() {
  st.renderAt = null;
  const stickyChanged = st.stickyRef !== st.sticky, animChanged = st.animRef !== st.anim;
  st.stickyRef = st.sticky; st.animRef = st.anim;
  if (stickyChanged || animChanged) st.pollE = 0;  // poll effect is re-created
  if (prevAnim !== st.anim) {
    if (st.effectOn) { viewport.removeEventListener('pointerdown', stopAnimation);
                       viewport.removeEventListener('wheel', stopAnimation); cancel(st.rafId); st.effectOn = false; }
    if (st.anim) { animate(viewport.scrollTop, 1);
                   viewport.addEventListener('pointerdown', stopAnimation);
                   viewport.addEventListener('wheel', stopAnimation); st.effectOn = true; }
    prevAnim = st.anim;
  }
}
viewport.addEventListener('scroll', () => throttled({timeStampLow: now}));
if (scenario.initialTop !== undefined) {
  // The reader had scrolled away earlier: Streamlit is no longer following the bottom.
  viewport._top = scenario.initialTop;
  st.sticky = st.stickyRef = false; st.anim = st.animRef = false; prevAnim = false;
  st.l = viewport.offsetHeight; st.u = viewport.scrollHeight;
} else {
  schedule(() => { setSticky(true); throttled({timeStampLow: now}); }, 0);
}
schedule(() => {
  if (st.stickyRef) {
    if (bottom()) st.pollE = 0;
    else if (st.pollE) { if (now - st.pollE > 34) { if (!st.animRef) { setAnim(true); setSticky(true); } st.pollE = 0; } }
    else st.pollE = now;
  } else if (viewport.scrollHeight <= viewport.offsetHeight && !st.stickyRef) setSticky(true);
}, 17, 17);

// ---------------------------------------------------------------- parent window + job
const windowListeners = {};
const parent = {
  document: {
    scrollingElement: viewport,
    getElementById(id) { return id === 'question-scroll-space' ? space : id.startsWith('question-') ? target : null; },
    querySelector(sel) { return sel.includes('stAppScrollToBottomContainer') ? viewport : null; },
  },
  getComputedStyle(el) { return {overflowY: el === viewport ? 'auto' : 'visible'}; },
  addEventListener(type, fn) { (windowListeners[type] ||= new Set()).add(fn); },
  removeEventListener(type, fn) { windowListeners[type]?.delete(fn); },
  WheelEvent: class { constructor(type, init) { this.type = type; Object.assign(this, init); } },
  setTimeout: (fn, ms) => schedule(fn, ms), clearTimeout: cancel,
};
const context = vm.createContext({
  window: {parent}, Math, JSON,
  setInterval: (fn, ms) => schedule(fn, ms, ms), clearInterval: cancel,
  setTimeout: (fn, ms) => schedule(fn, ms), clearTimeout: cancel,
});

for (const [time, by] of scenario.growth) schedule(() => grow(by), time);
schedule(() => vm.runInContext(job, context), scenario.jobStart);
if (scenario.restartAt) schedule(() => vm.runInContext(job, context), scenario.restartAt);
if (scenario.userScrollAt) schedule(() => {
  // A real wheel hits the container first, then bubbles to the window.
  emit('wheel', {});
  [...(windowListeners.wheel || [])].forEach(fn => fn({}));
  schedule(() => { viewport.scrollTop = scenario.userScrollTo; }, 5);
}, scenario.userScrollAt);

// ---------------------------------------------------------------- run
while (now <= scenario.duration) {
  let next = null;
  for (const [id, task] of tasks) if (!next || task.time < next[1].time || (task.time === next[1].time && id < next[0])) next = [id, task];
  if (!next || next[1].time > scenario.duration) break;
  const [id, task] = next;
  now = task.time;
  if (task.every) task.time = now + task.every; else tasks.delete(id);
  task.fn();
}
const destination = Math.max(0, targetPosition - 80);
let reversals = 0, lastDir = 0;
for (let k = 1; k < trace.length; k++) {
  const dir = Math.sign(trace[k][1] - trace[k - 1][1]);
  if (dir && lastDir && dir !== lastDir) reversals++;
  if (dir) lastDir = dir;
}
const afterSettle = trace.filter(([t]) => t > scenario.settledBy);
console.log(JSON.stringify({final: viewport.scrollTop, destination, reversals, moves: trace.length,
                            movesAfterSettle: afterSettle.length, sticky: st.stickyRef,
                            jobRunning: Boolean(parent.citrusQuestionScroll)}));
