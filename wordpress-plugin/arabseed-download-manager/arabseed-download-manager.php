<?php
/**
 * Plugin Name:       ArabSeed Download Manager
 * Plugin URI:        https://www.arabseedtech.org/
 * Description:       Add a download link to any post straight from the editor, drop in an SEO-friendly download button, and route visitors through a branded, redesigned countdown download page. No theme edits, no manual index.html.
 * Version:           1.1.0
 * Requires at least: 5.6
 * Requires PHP:      7.2
 * Author:            ArabSeed Tech
 * Author URI:        https://www.arabseedtech.org/
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       arabseed-download-manager
 * Domain Path:       /languages
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // No direct access.
}

define( 'ASDM_VERSION', '1.1.0' );
define( 'ASDM_FILE', __FILE__ );
define( 'ASDM_DIR', plugin_dir_path( __FILE__ ) );
define( 'ASDM_URL', plugin_dir_url( __FILE__ ) );
define( 'ASDM_BASENAME', plugin_basename( __FILE__ ) );

require_once ASDM_DIR . 'includes/class-asdm-settings.php';
require_once ASDM_DIR . 'includes/class-asdm-metabox.php';
require_once ASDM_DIR . 'includes/class-asdm-shortcode.php';
require_once ASDM_DIR . 'includes/class-asdm-download-page.php';

/**
 * Boot the plugin once WordPress is ready.
 */
function asdm_bootstrap() {
	load_plugin_textdomain( 'arabseed-download-manager', false, dirname( ASDM_BASENAME ) . '/languages' );

	ASDM_Settings::instance();
	ASDM_Metabox::instance();
	ASDM_Shortcode::instance();
	ASDM_Download_Page::instance();
}
add_action( 'plugins_loaded', 'asdm_bootstrap' );

/**
 * Activation: register rewrite rules for the download page, then flush.
 */
function asdm_activate() {
	require_once ASDM_DIR . 'includes/class-asdm-settings.php';
	require_once ASDM_DIR . 'includes/class-asdm-download-page.php';

	ASDM_Download_Page::instance()->register_rewrite_rules();
	flush_rewrite_rules();
}
register_activation_hook( __FILE__, 'asdm_activate' );

/**
 * Deactivation: clean up rewrite rules.
 */
function asdm_deactivate() {
	flush_rewrite_rules();
}
register_deactivation_hook( __FILE__, 'asdm_deactivate' );

/**
 * Quick link to the settings screen from the Plugins list.
 *
 * @param array $links Existing action links.
 * @return array
 */
function asdm_action_links( $links ) {
	$settings_link = sprintf(
		'<a href="%s">%s</a>',
		esc_url( admin_url( 'options-general.php?page=asdm-settings' ) ),
		esc_html__( 'Settings', 'arabseed-download-manager' )
	);
	array_unshift( $links, $settings_link );
	return $links;
}
add_filter( 'plugin_action_links_' . ASDM_BASENAME, 'asdm_action_links' );
