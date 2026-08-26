<?php
/**
 * Registers the /download/ endpoint, serves the redesigned download-page
 * template, and enqueues its assets. Replaces the manual index.html.
 *
 * @package ArabSeed_Download_Manager
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class ASDM_Download_Page {

	const QUERY_VAR = 'asdm_download_page';

	protected static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	protected function __construct() {
		add_action( 'init', array( $this, 'register_rewrite_rules' ) );
		add_filter( 'query_vars', array( $this, 'add_query_var' ) );
		add_action( 'template_redirect', array( $this, 'maybe_render' ) );
	}

	/**
	 * Register the rewrite rule for the configured slug.
	 *
	 * @param string $slug Optional slug override (used during save/activation).
	 */
	public function register_rewrite_rules( $slug = '' ) {
		if ( '' === $slug ) {
			$slug = ASDM_Settings::instance()->get( 'page_slug', 'download' );
		}
		$slug = sanitize_title( $slug );
		add_rewrite_rule( '^' . $slug . '/?$', 'index.php?' . self::QUERY_VAR . '=1', 'top' );
	}

	/**
	 * @param array $vars Registered query vars.
	 * @return array
	 */
	public function add_query_var( $vars ) {
		$vars[] = self::QUERY_VAR;
		return $vars;
	}

	/**
	 * If this is the download endpoint, render our template and stop.
	 */
	public function maybe_render() {
		if ( ! get_query_var( self::QUERY_VAR ) ) {
			return;
		}

		// Never index the gateway page: good SEO hygiene.
		if ( ! headers_sent() ) {
			header( 'X-Robots-Tag: noindex, nofollow', true );
			status_header( 200 );
		}

		$settings = ASDM_Settings::instance();

		// Config consumed by the template + front-end script.
		$config = array(
			'countdown'       => (int) $settings->get( 'countdown', 10 ),
			'brandName'       => $settings->get( 'brand_name', 'ArabSeed Tech' ),
			'logoUrl'         => $settings->get( 'logo_url', '' ),
			'defaultUrl'      => $settings->get( 'default_url', home_url( '/' ) ),
			'primaryColor'    => $settings->get( 'primary_color', '#182B5C' ),
			'backgroundColor' => $settings->get( 'background_color', '#FCF7EC' ),
			'heading'         => $settings->get( 'page_heading', 'جهزنا ملفك للتحميل' ),
			'subheading'      => $settings->get( 'page_subheading', 'شكراً لاختيارك المحتوى الحصري' ),
			'footerText'      => $settings->get( 'footer_text', 'ArabSeed Tech' ),
			'storageKey'      => 'arabseedDownloadURL',
			'titleKey'        => 'arabseedDownloadTitle',
			'homeUrl'         => home_url( '/' ),
			'year'            => gmdate( 'Y' ),
		);

		// Expose to the template scope.
		set_query_var( 'asdm_config', $config );

		$template = ASDM_DIR . 'templates/download-page.php';
		if ( file_exists( $template ) ) {
			include $template;
		}
		exit;
	}
}
