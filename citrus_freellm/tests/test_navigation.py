"""Exercise scroll jobs against viewport geometry and delayed layout changes."""
import json
import shutil
import subprocess
import unittest

from citrus_freellm.navigation import scroll_script


@unittest.skipUnless(shutil.which('node'), 'Node is required for scroll geometry checks')
class NavigationTests(unittest.TestCase):
    def test_short_answer_delayed_layout_consecutive_job_and_manual_stop(self):
        first = scroll_script(0, 1).removeprefix('<script>').removesuffix('</script>')
        second = scroll_script(2, 2).removeprefix('<script>').removesuffix('</script>')
        script = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const listeners = new Map(), timers = new Map();
let serial = 0, contentHeight = 1100, targetPosition = 1000;
const space = {style: {height: '0px'}, get offsetHeight() {return parseFloat(this.style.height)}};
const viewport = {
  parentElement: null, scrollTop: 0, clientHeight: 600,
  get scrollHeight() {return contentHeight + space.offsetHeight},
  getBoundingClientRect() {return {top: 0}},
  scrollTo({top}) {this.scrollTop = Math.min(top, this.scrollHeight - this.clientHeight)},
};
const wrapper = {parentElement: viewport};
const target = {parentElement: wrapper, getBoundingClientRect() {return {top: targetPosition - viewport.scrollTop}}};
const document = {
  scrollingElement: viewport,
  getElementById(id) {return id === 'question-scroll-space' ? space : target},
};
const parent = {
  document,
  getComputedStyle(el) {return {overflowY: el === viewport ? 'auto' : 'visible'}},
  addEventListener(type, fn) {listeners.set(type, fn)},
  removeEventListener(type, fn) {if (listeners.get(type) === fn) listeners.delete(type)},
};
const context = vm.createContext({
  window: {parent},
  setInterval(fn) {timers.set(++serial, fn); return serial},
  clearInterval(id) {timers.delete(id)},
});
const tick = () => [...timers.values()].forEach(fn => fn());
vm.runInContext(FIRST, context);
assert.equal(viewport.scrollTop, 920, 'short answer has room to align question');
viewport.scrollTop = viewport.scrollHeight - viewport.clientHeight;
contentHeight += 900;  // A chart changes layout after the first paint.
tick();
assert.equal(viewport.scrollTop, 920, 'correct late bottom-following');
targetPosition = 1800;
vm.runInContext(SECOND, context);
assert.equal(timers.size, 1, 'consecutive submission cancels previous job');
assert.equal(viewport.scrollTop, 1720, 'consecutive question has its own target');
listeners.get('wheel')();
viewport.scrollTop = 350;
tick();
assert.equal(viewport.scrollTop, 350, 'manual scroll is respected');
assert.equal(timers.size, 0);
assert.equal(listeners.size, 0);
assert.equal(parent.citrusQuestionScroll, undefined);
'''.replace('FIRST', json.dumps(first)).replace('SECOND', json.dumps(second))
        completed = subprocess.run([shutil.which('node'), '-'], input=script, capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
