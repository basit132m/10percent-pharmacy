/**
 * ArabSeed download button.
 *
 * Keeps the original behaviour: on click, store the real link in
 * sessionStorage and open the download page. The link, file title and
 * feature image are also passed as URL-safe fragment params so direct/shared
 * page loads still resolve them.
 */
(function () {
	'use strict';

	var cfg = window.ASDM_BTN || {};
	var pageUrl = cfg.pageUrl || '/download/';
	var storageKey = cfg.storageKey || 'arabseedDownloadURL';
	var titleKey = cfg.titleKey || 'arabseedDownloadTitle';
	var imageKey = cfg.imageKey || 'arabseedDownloadImage';

	function b64url(str) {
		try {
			return btoa(unescape(encodeURIComponent(str)))
				.replace(/\+/g, '-')
				.replace(/\//g, '_')
				.replace(/=+$/, '');
		} catch (e) {
			return '';
		}
	}

	function store(key, value) {
		try {
			if (value) {
				sessionStorage.setItem(key, value);
			} else {
				sessionStorage.removeItem(key);
			}
		} catch (e) {
			/* sessionStorage may be blocked; fragment fallback still works. */
		}
	}

	function go(url, title, image) {
		if (!url) {
			return;
		}
		store(storageKey, url);
		store(titleKey, title);
		store(imageKey, image);

		var params = [];
		var fu = b64url(url);
		if (fu) { params.push('u=' + fu); }
		var ft = b64url(title);
		if (ft) { params.push('t=' + ft); }
		var fi = b64url(image);
		if (fi) { params.push('i=' + fi); }

		var target = pageUrl;
		if (params.length) {
			target += (pageUrl.indexOf('#') === -1 ? '#' : '&') + params.join('&');
		}

		// Open the download page in a new tab (keeps the article open).
		var win = window.open(target, '_blank');
		if (win) {
			win.opener = null;
		} else {
			// Popup blocked -> fall back to same-tab navigation.
			window.location.href = target;
		}
	}

	function onClick(e) {
		var btn = e.currentTarget;
		var url = btn.getAttribute('data-download-url');
		var title = btn.getAttribute('data-download-title') || '';
		var image = btn.getAttribute('data-download-image') || '';
		if (url) {
			e.preventDefault();
			go(url, title, image);
		}
	}

	function init() {
		var buttons = document.querySelectorAll('.js-asdm-download');
		for (var i = 0; i < buttons.length; i++) {
			buttons[i].addEventListener('click', onClick);
		}
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	} else {
		init();
	}
})();
