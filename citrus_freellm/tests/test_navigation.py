"""Exercise scroll jobs against a model of Streamlit's bottom-following chat container.

scroll_sim.js reproduces Streamlit 1.67's sticky-bottom hook (animation, 17 ms poll,
throttled scroll handler, wheel cancel) in virtual time, so a job that fights it
shows up as the page bouncing up and down while charts render.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from citrus_freellm.navigation import scroll_script

SIM = Path(__file__).with_name('scroll_sim.js')
BASE = {'contentHeight': 1300, 'targetPosition': 1000, 'jobStart': 40, 'growth': [],
        'duration': 8000, 'settledBy': 4500}
DESTINATION = 920  # target 1000 − 80 px header margin


@unittest.skipUnless(shutil.which('node'), 'Node is required for scroll geometry checks')
class NavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.job = Path(cls.folder.name) / 'job.js'
        cls.job.write_text(scroll_script(3, 1).removeprefix('<script>').removesuffix('</script>'), encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def simulate(self, **scenario):
        path = Path(self.folder.name) / 'scenario.json'
        path.write_text(json.dumps({**BASE, **scenario}), encoding='utf-8')
        completed = subprocess.run([shutil.which('node'), str(SIM), str(self.job), str(path)],
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def assert_settles_once(self, report):
        self.assertEqual(report['final'], DESTINATION)
        # Down while Streamlit follows the growing answer, then one move up. No bouncing.
        self.assertLessEqual(report['reversals'], 1, report)
        self.assertEqual(report['movesAfterSettle'], 0, report)
        self.assertFalse(report['sticky'], 'Streamlit must stop following the bottom')
        self.assertFalse(report['jobRunning'])

    def test_charts_rendering_late_do_not_bounce(self):
        self.assert_settles_once(self.simulate(growth=[[150, 350], [400, 420], [700, 380], [1100, 300]]))

    def test_short_answer_gets_room_to_align_question(self):
        self.assert_settles_once(self.simulate(contentHeight=1150))

    def test_long_answer(self):
        self.assert_settles_once(self.simulate(contentHeight=2400, growth=[[200, 400], [600, 400]]))

    def test_growth_after_settling_does_not_pull_page_down(self):
        self.assert_settles_once(self.simulate(growth=[[150, 350], [400, 420], [2600, 500]], duration=9000))

    def test_consecutive_submission_replaces_previous_job(self):
        self.assert_settles_once(self.simulate(growth=[[150, 350], [400, 420]], restartAt=250))

    def test_clicked_suggestion_mid_page_moves_to_new_question(self):
        # The reader scrolled up earlier, so Streamlit no longer follows the bottom.
        report = self.simulate(contentHeight=3000, targetPosition=2500, initialTop=1900)
        self.assertEqual(report['final'], 2420)
        self.assertEqual(report['moves'], 1)
        self.assertFalse(report['jobRunning'])

    def test_layout_that_never_stops_wobbling_still_moves(self):
        # Icon fonts or responsive charts can keep nudging the height by a pixel.
        wobble = [[t, 1 if (t // 100) % 2 == 0 else -1] for t in range(100, 8000, 100)]
        report = self.simulate(contentHeight=3000, targetPosition=2500, initialTop=1900,
                               growth=wobble, settledBy=7000)
        self.assertEqual(report['final'], 2420)
        self.assertEqual(report['reversals'], 0)

    def test_manual_scroll_stops_job_and_is_respected(self):
        report = self.simulate(growth=[[150, 350]], userScrollAt=380, userScrollTo=300, duration=6000, settledBy=2000)
        self.assertEqual(report['final'], 300)
        self.assertFalse(report['jobRunning'])
        self.assertEqual(report['movesAfterSettle'], 0)


if __name__ == '__main__':
    unittest.main()
