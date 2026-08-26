<?php
/**
 * [arabseed_download] shortcode + matching Gutenberg block.
 *
 * Renders the download button. On click it stores the target link in
 * sessionStorage (same behaviour the site already relied on) and sends the
 * visitor to the plugin's download page.
 *
 * @package ArabSeed_Download_Manager
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class ASDM_Shortcode {

	protected static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	protected function __construct() {
		add_shortcode( 'arabseed_download', array( $this, 'render' ) );
		add_action( 'wp_enqueue_scripts', array( $this, 'register_assets' ) );
		add_action( 'init', array( $this, 'register_block' ) );
	}

	public function register_assets() {
		wp_register_style( 'asdm-button', ASDM_URL . 'assets/css/asdm-button.css', array(), ASDM_VERSION );
		wp_register_script( 'asdm-button', ASDM_URL . 'assets/js/asdm-button.js', array(), ASDM_VERSION, true );

		$settings = ASDM_Settings::instance();
		wp_localize_script(
			'asdm-button',
			'ASDM_BTN',
			array(
				'pageUrl'    => home_url( '/' . $settings->get( 'page_slug', 'download' ) . '/' ),
				'storageKey' => 'arabseedDownloadURL',
				'titleKey'   => 'arabseedDownloadTitle',
			)
		);
	}

	/**
	 * Register a thin block that reuses the shortcode render callback.
	 */
	public function register_block() {
		if ( ! function_exists( 'register_block_type' ) ) {
			return;
		}

		wp_register_script(
			'asdm-block',
			ASDM_URL . 'assets/js/asdm-block.js',
			array( 'wp-blocks', 'wp-element', 'wp-block-editor', 'wp-components', 'wp-i18n' ),
			ASDM_VERSION,
			true
		);

		register_block_type(
			'arabseed/download-button',
			array(
				'api_version'     => 2,
				'editor_script'   => 'asdm-block',
				'render_callback' => array( $this, 'render_block' ),
				'attributes'      => array(
					'url'     => array( 'type' => 'string', 'default' => '' ),
					'altUrl'  => array( 'type' => 'string', 'default' => '' ),
					'text'    => array( 'type' => 'string', 'default' => '' ),
					'align'   => array( 'type' => 'string', 'default' => 'center' ),
				),
			)
		);
	}

	/**
	 * Block render callback -> map to shortcode attributes.
	 *
	 * @param array $attributes Block attributes.
	 * @return string
	 */
	public function render_block( $attributes ) {
		return $this->render(
			array(
				'url'     => isset( $attributes['url'] ) ? $attributes['url'] : '',
				'alt_url' => isset( $attributes['altUrl'] ) ? $attributes['altUrl'] : '',
				'text'    => isset( $attributes['text'] ) ? $attributes['text'] : '',
				'align'   => isset( $attributes['align'] ) ? $attributes['align'] : 'center',
			)
		);
	}

	/**
	 * Shortcode render callback.
	 *
	 * @param array $atts Shortcode attributes.
	 * @return string
	 */
	public function render( $atts ) {
		$settings = ASDM_Settings::instance();

		$atts = shortcode_atts(
			array(
				'url'     => '',
				'alt_url' => '',
				'text'    => '',
				'align'   => 'center',
			),
			$atts,
			'arabseed_download'
		);

		// Fall back to the current post's meta.
		$post_id = get_the_ID();
		if ( '' === $atts['url'] && $post_id ) {
			$atts['url'] = get_post_meta( $post_id, ASDM_Metabox::META_URL, true );
		}
		if ( '' === $atts['alt_url'] && $post_id ) {
			$atts['alt_url'] = get_post_meta( $post_id, ASDM_Metabox::META_ALT, true );
		}
		if ( '' === $atts['text'] && $post_id ) {
			$atts['text'] = get_post_meta( $post_id, ASDM_Metabox::META_TEXT, true );
		}

		$url     = esc_url( $atts['url'] );
		$alt_url = esc_url( $atts['alt_url'] );
		$text    = $atts['text'] ? $atts['text'] : $settings->get( 'button_text', __( 'تحميل', 'arabseed-download-manager' ) );
		$alt_txt = $settings->get( 'alt_button_text', 'الرابط البديل !' );

		if ( '' === $url && '' === $alt_url ) {
			if ( current_user_can( 'edit_posts' ) ) {
				return '<p style="color:#b32d2e;font-weight:600">' . esc_html__( 'ArabSeed Download: add a download link in the "ArabSeed Download" box (only editors see this notice).', 'arabseed-download-manager' ) . '</p>';
			}
			return '';
		}

		// File name for a nicer download-page title (optional).
		$file = $post_id ? get_post_meta( $post_id, ASDM_Metabox::META_FILE, true ) : '';
		if ( ! $file && $post_id ) {
			$file = get_the_title( $post_id );
		}

		wp_enqueue_style( 'asdm-button' );
		wp_enqueue_script( 'asdm-button' );

		$align = in_array( $atts['align'], array( 'left', 'right', 'center' ), true ) ? $atts['align'] : 'center';

		ob_start();
		?>
		<div class="asdm-download" data-align="<?php echo esc_attr( $align ); ?>">
			<button type="button" class="asdm-btn asdm-btn--icon js-asdm-download"
				data-download-url="<?php echo $url; // esc_url above ?>"
				data-download-title="<?php echo esc_attr( $file ); ?>"
				aria-label="<?php echo esc_attr( $text ); ?>">
				<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">
					<path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v9.586l2.293-2.293a1 1 0 0 1 1.414 1.414l-4 4a1 1 0 0 1-1.414 0l-4-4a1 1 0 1 1 1.414-1.414L11 13.586V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v1h12v-1a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z"/>
				</svg>
			</button>

			<button type="button" class="asdm-btn asdm-btn--main js-asdm-download"
				data-download-url="<?php echo $url; ?>"
				data-download-title="<?php echo esc_attr( $file ); ?>">
				<span class="asdm-btn__label"><?php echo esc_html( $text ); ?></span>
			</button>

			<?php if ( $alt_url ) : ?>
			<button type="button" class="asdm-btn asdm-btn--alt js-asdm-download"
				data-download-url="<?php echo $alt_url; ?>"
				data-download-title="<?php echo esc_attr( $file ); ?>">
				<span class="asdm-btn__label"><?php echo esc_html( $alt_txt ); ?></span>
			</button>
			<?php endif; ?>
		</div>
		<?php
		return trim( ob_get_clean() );
	}
}
