"""Scroll to a submitted question once; never include user text in JavaScript."""

# Both the current iframe API and the compatibility renderer receive a positive
# pixel height. Zero is rejected by Streamlit's layout validation.
SCROLL_FRAME_HEIGHT = 1


def question_anchor(index):
    return f'question-{int(index)}'


def scroll_script(index, nonce):
    index, nonce = int(index), int(nonce)
    return f'''<script>
    // Submission {nonce}: each submission owns a fresh iframe and scroll job.
    (() => {{
      const parentWindow = window.parent;
      const doc = parentWindow.document;
      if (parentWindow.citrusQuestionScroll) parentWindow.citrusQuestionScroll();
      let tries = 0, timer, stopped = false;
      const stop = () => {{
        stopped = true;
        clearInterval(timer);
        parentWindow.removeEventListener('wheel', stop);
        parentWindow.removeEventListener('touchstart', stop);
        parentWindow.removeEventListener('keydown', stop);
        if (parentWindow.citrusQuestionScroll === stop) delete parentWindow.citrusQuestionScroll;
      }};
      parentWindow.citrusQuestionScroll = stop;
      const move = () => {{
        if (stopped) return;
        try {{
          const target = doc.getElementById('question-{index}');
          const space = doc.getElementById('question-scroll-space');
          if (target && space) {{
            // Scroll Streamlit's actual viewport, not the iframe or the page body.
            let viewport = target.parentElement;
            while (viewport && !/auto|scroll/.test(parentWindow.getComputedStyle(viewport).overflowY)) {{
              viewport = viewport.parentElement;
            }}
            viewport = viewport || doc.scrollingElement;
            const top = viewport === doc.scrollingElement ? 0 : viewport.getBoundingClientRect().top;
            const destination = Math.max(0, viewport.scrollTop + target.getBoundingClientRect().top - top - 80);
            // Short answers also need enough room below them to align the question.
            const available = viewport.scrollHeight - viewport.clientHeight - space.offsetHeight;
            const needed = Math.ceil(Math.max(0, destination - available));
            if (space.style.height !== needed + 'px') space.style.height = needed + 'px';
            viewport.scrollTo({{top: destination, behavior: 'instant'}});
          }}
        }} catch (error) {{ stop(); }}
        // Charts and Streamlit's own bottom-following can settle after initial paint.
        if (++tries >= 50) stop();
      }};
      parentWindow.addEventListener('wheel', stop, {{passive: true}});
      parentWindow.addEventListener('touchstart', stop, {{passive: true}});
      parentWindow.addEventListener('keydown', stop);
      timer = setInterval(move, 100);
      move();
    }})();
    </script>'''
