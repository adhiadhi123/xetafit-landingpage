/* One scroll pass; one tablet. No wheel interception or layout writes. */
(() => {
  const section = document.querySelector('#benefits');
  if (!section || !Element.prototype.animate || !window.IntersectionObserver) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const art = section.querySelector('.formula__art');
  const find = selector => section.querySelector(selector);
  const motions = [];
  let frame = 0;
  let nearby = false;
  const ease = 'cubic-bezier(.22, 1, .36, 1)';
  function add(element, frames, duration, delay = 0, easing = ease) {
    const animation = element.animate(frames, { duration, delay, easing, fill: 'both' });
    animation.pause();
    animation.currentTime = 0;
    motions.push(animation);
  }
  function update() {
    frame = 0;
    if (!motions.length) return;
    // Start only once the section is on screen AND the tube opening is clearly
    // visible. Read geometry together before writing animation times.
    const sectionTop = section.getBoundingClientRect().top;
    const bounds = art.getBoundingClientRect();
    const mouthTop = bounds.top + bounds.height * .28;
    const sectionProgress = (innerHeight * .16 - sectionTop) / (innerHeight * .45);
    const mouthProgress = (innerHeight * .75 - mouthTop) / (innerHeight * .45);
    const progress = Math.max(0, Math.min(1, sectionProgress, mouthProgress));
    for (const motion of motions) motion.currentTime = progress * 1000;
    section.classList.toggle('benefits--settled', progress === 1);
  }
  function schedule() {
    if (!frame && motions.length) frame = requestAnimationFrame(update);
  }
  function setup() {
    for (const motion of motions) motion.cancel();
    motions.length = 0;
    section.classList.remove('benefits--animated', 'benefits--settled');
    if (reduced.matches) return;
    try {
      add(find('.benefit-cap'), [
        { transform: 'translateY(0)', opacity: 1 },
        { transform: 'translateY(-27cqh)', opacity: 1 }
      ], 280);
      add(find('.benefit-cap .benefit-sprite'), [
        { transform: 'rotate(-22deg)' }, { transform: 'rotate(-4deg)' }
      ], 280);
      add(find('.benefit-cap'), [{ opacity: 0 }, { opacity: 1 }], 1, 1, 'steps(1, end)');
      add(find('.benefit-seal'), [{ opacity: 1 }, { opacity: 0 }], 1, 1, 'steps(1, end)');
      add(find('.benefit-flight'), [
        { offset: 0, opacity: 0, transform: 'translate(0, 0)', zIndex: 1 },
        { offset: .12, opacity: 1, transform: 'translate(0, -2cqh)', zIndex: 1 },
        { offset: .45, opacity: 1, transform: 'translate(0, -12cqh)', zIndex: 1 },
        { offset: .451, opacity: 1, transform: 'translate(0, -12cqh)', zIndex: 3 },
        { offset: 1, opacity: 1, transform: 'translate(12cqh, -15cqh)', zIndex: 3 }
      ], 340, 280, 'linear');
      [...section.querySelectorAll('.bfact')].forEach((benefit, index) => {
        add(benefit, [{ opacity: 0, transform: 'translateY(12px)' },
          { opacity: 1, transform: 'translateY(0)' }], 200, 570 + index * 40);
      });
      section.classList.add('benefits--animated');
      schedule();
    } catch {
      // If animation setup fails, retain the fully readable static composition.
      for (const motion of motions) motion.cancel();
      motions.length = 0;
      section.classList.remove('benefits--animated');
    }
  }
  const observer = new IntersectionObserver(entries => {
    nearby = entries[0].isIntersecting;
    schedule();
  }, { rootMargin: '0px' });
  observer.observe(section);
  addEventListener('scroll', () => { if (nearby) schedule(); }, { passive: true });
  addEventListener('resize', schedule, { passive: true });
  addEventListener('pageshow', schedule);
  reduced.addEventListener('change', setup);
  setup();
})();
