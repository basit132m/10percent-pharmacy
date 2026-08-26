/**
 * ArabSeed download page.
 *
 * Same logic as the original index.html: run a countdown, then reveal the
 * download button which redirects to the stored link. Source of the link,
 * in order: sessionStorage -> URL fragment (#u=base64url) -> configured
 * fallback URL.
 */
(function () {
	'use strict';

	var cfg = window.ASDM || {};
	var total = parseInt(cfg.countdown, 10);
	if (isNaN(total) || total < 0) {
		total = 10;
	}
	var storageKey = cfg.storageKey || 'arabseedDownloadURL';
	var titleKey = cfg.titleKey || 'arabseedDownloadTitle';
	var fallback = cfg.defaultUrl || cfg.homeUrl || '/';

	var countEl = document.getElementById('asdm-count');
	var statusEl = document.getElementById('asdm-status');
	var circle = document.getElementById('asdm-progress');
	var btn = document.getElementById('asdm-download');
	var timer = document.querySelector('.asdm-timer');

	var RADIUS = 71;
	var CIRCUMFERENCE = 2 * Math.PI * RADIUS;

	if (circle) {
		circle.style.strokeDasharray = CIRCUMFERENCE;
		circle.style.strokeDashoffset = '0';
	}

	function fromFragment() {
		var m = (window.location.hash || '').match(/[#&]u=([^&]+)/);
		if (!m) {
			return '';
		}
		try {
			var s = m[1].replace(/-/g, '+').replace(/_/g, '/');
			while (s.length % 4) {
				s += '=';
			}
			return decodeURIComponent(escape(atob(s)));
		} catch (e) {
			return '';
		}
	}

	function resolveUrl() {
		var url = '';
		try {
			url = sessionStorage.getItem(storageKey) || '';
		} catch (e) {
			url = '';
		}
		if (!url) {
			url = fromFragment();
		}
		return url || fallback;
	}

	var downloadURL = resolveUrl();
	var remaining = total;

	function render(value) {
		if (countEl) {
			countEl.textContent = toArabicDigits(value);
		}
		if (circle) {
			var progress = total > 0 ? (total - value) / total : 1;
			circle.style.strokeDashoffset = CIRCUMFERENCE * progress;
		}
		if (statusEl) {
			statusEl.textContent = value > 0
				? 'جاري التجهيز ... ' + toArabicDigits(value) + ' ث'
				: 'الملف جاهز !';
		}
	}

	function toArabicDigits(n) {
		var map = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
		return String(n).replace(/\d/g, function (d) {
			return map[d];
		});
	}

	function reveal() {
		if (btn) {
			btn.href = downloadURL;
			btn.classList.remove('is-hidden');
		}
		if (timer) {
			timer.setAttribute('data-state', 'ready');
		}
		if (statusEl) {
			statusEl.textContent = 'اضغط زر التحميل';
		}
	}

	render(remaining);

	if (remaining <= 0) {
		reveal();
	} else {
		var interval = setInterval(function () {
			remaining -= 1;
			render(remaining);
			if (remaining <= 0) {
				clearInterval(interval);
				reveal();
			}
		}, 1000);
	}

	if (btn) {
		btn.addEventListener('click', function (e) {
			e.preventDefault();
			window.location.href = downloadURL;
		});
	}
})();
