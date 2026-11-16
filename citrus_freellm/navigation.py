"""Scroll to a submitted question once; never include user text in JavaScript."""

# Both the current iframe API and the compatibility renderer receive a positive
# pixel height. Zero is rejected by Streamlit's layout validation.
SCROLL_FRAME_HEIGHT = 1


def question_anchor(index):
    return f'question-{int(index)}'


def scroll_script(index, nonce):
    """Move to the submitted question once the page stops growing.

    Streamlit's chat container follows the bottom while it is "sticky": whenever
    the content height changes (charts render late) it animates back down. A job
    that keeps pulling the view up fights that animation and the page bounces.
    So this job lets Streamlit follow the growth, waits until the layout has been
    still for a moment, then moves once. Streamlit stops following only when it
    sees a scroll away from the bottom with unchanged heights, after a wheel
    event cancelled its animation — the same signals a reader's scroll produces.
    """
    index, nonce = int(index), int(nonce)
    return f'''<script>
    // Submission {nonce}: each submission owns a fresh iframe and scroll job.
    (() => {{
      const parentWindow = window.parent;
      const doc = parentWindow.document;
      if (parentWindow.citrusQuestionScroll) parentWindow.citrusQuestionScroll();
      // Fonts, icons and responsive charts can keep nudging the layout by a pixel or
      // two forever, so "still" allows a small wobble and a slow page moves anyway.
      const STILL_FOLLOWING = 5, STILL_IDLE = 3, FORCE_FOLLOWING = 30, FORCE_IDLE = 8, WOBBLE = 4, MAX_TICKS = 80, MAX_JUMPS = 4, MARGIN = 8;
      let ticks = 0, still = 0, waitedFollowing = 0, waitedIdle = 0, jumps = 0, held = 0, timer, stopped = false, jumping = false, last = null;
      const stop = () => {{
        stopped = true;
        clearInterval(timer);
        parentWindow.removeEventListener('wheel', stop);
        parentWindow.removeEventListener('touchstart', stop);
        parentWindow.removeEventListener('keydown', stop);
        if (parentWindow.citrusQuestionScroll === stop) delete parentWindow.citrusQuestionScroll;
      }};
      parentWindow.citrusQuestionScroll = stop;
      const geometry = () => {{
        const target = doc.getElementById('question-{index}');
        const space = doc.getElementById('question-scroll-space');
        if (!target || !space) return null;
        // Scroll Streamlit's actual viewport, not the iframe or the page body.
        let viewport = target.parentElement;
        while (viewport && !/auto|scroll/.test(parentWindow.getComputedStyle(viewport).overflowY)) {{
          viewport = viewport.parentElement;
        }}
        viewport = viewport || doc.scrollingElement;
        const top = viewport === doc.scrollingElement ? 0 : viewport.getBoundingClientRect().top;
        const destination = Math.max(0, Math.round(viewport.scrollTop + target.getBoundingClientRect().top - top - 80));
        // Short answers need room below them. Keep a margin so the question is
        // never exactly "at the bottom", where Streamlit would stay sticky.
        const available = viewport.scrollHeight - viewport.clientHeight - space.offsetHeight;
        const needed = destination > available - MARGIN ? Math.ceil(destination - available) + MARGIN : 0;
        return {{viewport, space, destination, needed: Math.max(0, needed)}};
      }};
      const jump = (g) => {{
        // A non-bubbling wheel cancels Streamlit's animation without reaching the
        // reader-scroll listeners above. The scroll must come a moment later:
        // Streamlit ignores scroll events stamped at or before that wheel.
        jumping = true;
        jumps++;
        g.viewport.dispatchEvent(new parentWindow.WheelEvent('wheel', {{bubbles: false}}));
        parentWindow.setTimeout(() => {{
          jumping = false;
          if (stopped) return;
          const now = geometry();
          if (now) now.viewport.scrollTo({{top: now.destination, behavior: 'instant'}});
        }}, 30);
      }};
      const tick = () => {{
        if (stopped || jumping) return;
        if (++ticks > MAX_TICKS || jumps > MAX_JUMPS) return stop();
        try {{
          const g = geometry();
          if (!g) return;
          const onTarget = Math.abs(g.viewport.scrollTop - g.destination) <= 1;
          if (onTarget) {{
            // Stay a little while: a late chart may still pull the page down.
            if (++held >= 15) stop();
            return;
          }}
          held = 0;
          const shape = [g.viewport.scrollHeight - g.space.offsetHeight, g.viewport.scrollTop];
          const moved = last ? Math.abs(shape[1] - last[1]) : 0;
          const steady = last && Math.abs(shape[0] - last[0]) <= WOBBLE && moved <= WOBBLE;
          still = steady ? still + 1 : 0;
          last = shape;
          // At (or animating towards) the bottom, Streamlit is following a growing
          // answer: give it time. Mid-page and motionless (e.g. after clicking a
          // suggested question) nothing follows, so go sooner.
          const atBottom = g.viewport.scrollHeight - g.viewport.scrollTop - g.viewport.clientHeight < 2;
          const following = atBottom || moved > WOBBLE;
          if (following) {{ waitedIdle = 0; waitedFollowing++; }} else waitedIdle++;
          const settled = still >= (following ? STILL_FOLLOWING : STILL_IDLE);
          if (!settled && waitedFollowing < FORCE_FOLLOWING && waitedIdle < FORCE_IDLE) return;
          still = 0;
          waitedFollowing = 0;
          waitedIdle = 0;
          // Resize the room below only once growth has stopped, then let Streamlit
          // settle on it before moving. Grow it when short, clear it when unused;
          // a few spare pixels are fine (re-sizing for every wobble never ends).
          const room = g.space.offsetHeight;
          if (g.needed - room > 0 || (g.needed === 0 && room > 0)) {{
            g.space.style.height = (g.needed ? g.needed + WOBBLE : 0) + 'px';
            return;
          }}
          jump(g);
        }} catch (error) {{ stop(); }}
      }};
      parentWindow.addEventListener('wheel', stop, {{passive: true}});
      parentWindow.addEventListener('touchstart', stop, {{passive: true}});
      parentWindow.addEventListener('keydown', stop);
      timer = setInterval(tick, 100);
      tick();
    }})();
    </script>'''
