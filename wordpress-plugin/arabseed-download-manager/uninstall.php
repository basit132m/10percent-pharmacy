<?php
/**
 * Uninstall cleanup: remove plugin options and post meta.
 *
 * @package ArabSeed_Download_Manager
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'asdm_settings' );

global $wpdb;
$wpdb->query(
	"DELETE FROM {$wpdb->postmeta} WHERE meta_key IN (
		'_asdm_download_url',
		'_asdm_alt_url',
		'_asdm_button_text',
		'_asdm_feature_image',
		'_asdm_file_name'
	)"
);

flush_rewrite_rules();
