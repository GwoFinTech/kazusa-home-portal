/* QR scan-login confirm page behaviour.
 * All server data arrives through data-* attributes on <body>, so this file
 * never mixes Python string formatting with JS braces. */
(function () {
  const body = document.body;
  const cfg = body.dataset;
  const T = JSON.parse(cfg.i18n || '{}');
  const SID = cfg.sid || '';
  const CSRF = cfg.csrf || '';
  const PORTAL = cfg.portalUrl || '/';

  const btn = document.getElementById('confirm-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const msg = document.getElementById('msg');

  function showMsg(text, ok) {
    msg.style.display = 'block';
    msg.className = ok ? 'msg msg-ok' : 'msg msg-err';
    msg.textContent = text;
  }

  cancelBtn.addEventListener('click', function () {
    window.location.href = PORTAL;
  });

  btn.addEventListener('click', async function () {
    btn.disabled = true;
    btn.textContent = T.authorizing || '';
    try {
      const r = await fetch('/auth/qr/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF },
        body: JSON.stringify({ sid: SID }),
      });
      const data = await r.json();
      if (data.ok) {
        showMsg(T.confirmSent || '', true);
        btn.textContent = (T.backPortal || '').replace('{sec}', 3);
        btn.disabled = false;
        cancelBtn.style.display = 'none';
        btn.onclick = function () { window.location.href = PORTAL; };
        var sec = 3;
        var timer = setInterval(function () {
          sec--;
          if (sec <= 0) {
            clearInterval(timer);
            window.location.href = PORTAL;
          } else {
            btn.textContent = (T.backPortal || '').replace('{sec}', sec);
          }
        }, 1000);
      } else {
        showMsg(data.error || T.authFailed || '', false);
        btn.disabled = false;
        btn.textContent = T.retry || '';
      }
    } catch (e) {
      showMsg(T.networkError || '', false);
      btn.disabled = false;
      btn.textContent = T.retry || '';
    }
  });
})();
