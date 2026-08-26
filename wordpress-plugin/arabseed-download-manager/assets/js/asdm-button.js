/**
 * ArabSeed download button.
 *
 * Keeps the original behaviour: on click, store the real link in
 * sessionStorage and send the visitor to the download page. The link is also
 * passed as a URL-safe fragment so direct/shared page loads still resolve it.
 */
(function () {
	'use strict';

	var cfg = window.ASDM_BTN || {};
	var pageUrl = cfg.pageUrl || '/download/';
	var storageKey = cfg.storageKey || 'arabseedDownloadURL';
	var titleKey = cfg.titleKey || 'arabseedDownloadTitle';

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

	function go(url, title) {
		if (!url) {
			return;
		}
		try {
			sessionStorage.setItem(storageKey, url);
			if (title) {
				sessionStorage.setItem(titleKey, title);
			}
		} catch (e) {
			/* sessionStorage may be blocked; fragment fallback still works. */
		}

		var target = pageUrl;
		var frag = b64url(url);
		if (frag) {
			target += (pageUrl.indexOf('#') === -1 ? '#u=' : '&u=') + frag;
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
		if (url) {
			e.preventDefault();
			go(url, title);
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
