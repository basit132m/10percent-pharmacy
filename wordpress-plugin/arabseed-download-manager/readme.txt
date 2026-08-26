=== ArabSeed Download Manager ===
Contributors: arabseedtech
Tags: download, download button, download timer, download page, seo
Requires at least: 5.6
Tested up to: 6.6
Requires PHP: 7.2
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Add a download link to any post from the editor, drop in an SEO-friendly
download button, and route visitors through a branded countdown download page.

== Description ==

ArabSeed Download Manager lets you manage download links straight from the
WordPress admin — no theme edits and no manual index.html file.

* An "ArabSeed Download" box in the post editor to store the download link,
  an optional alternative link, a feature image and a button label.
* A `[arabseed_download]` shortcode (and matching block) that outputs the
  download button.
* A managed, redesigned download page served at `/download/` with the same
  countdown -> reveal -> redirect behaviour, styled from your brand settings.
* A Settings screen (Settings > ArabSeed Download) for brand name, logo,
  colours, countdown length, page slug and copy.

The download (gateway) page is served with `noindex, nofollow`, while your
content pages keep clean, semantic, crawlable markup — good SEO hygiene.

== Installation ==

1. Upload the `arabseed-download-manager` folder to `/wp-content/plugins/`.
2. Activate the plugin through the "Plugins" menu in WordPress.
3. Visit Settings > ArabSeed Download to set your brand and options.
4. Edit a post, paste the link into the "ArabSeed Download" box, and add the
   `[arabseed_download]` shortcode where you want the button.

== Frequently Asked Questions ==

= Where does the download page live? =
At `/download/` by default. Change the slug on the settings screen; the plugin
refreshes the permalink for you when you save.

= Do I still need my old index.html? =
No. The plugin renders the page for you. You can keep the old file as a backup,
but the `/download/` URL is now handled by WordPress.

== Changelog ==

= 1.0.0 =
* Initial release.
