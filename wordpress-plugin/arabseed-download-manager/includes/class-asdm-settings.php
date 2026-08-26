<?php
/**
 * Plugin settings: stores brand + download-page options and renders the
 * Settings > ArabSeed Download admin screen.
 *
 * @package ArabSeed_Download_Manager
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class ASDM_Settings {

	const OPTION_KEY = 'asdm_settings';

	/**
	 * @var ASDM_Settings|null
	 */
	protected static $instance = null;

	/**
	 * Cached options.
	 *
	 * @var array|null
	 */
	protected $options = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	protected function __construct() {
		add_action( 'admin_menu', array( $this, 'add_settings_page' ) );
		add_action( 'admin_init', array( $this, 'register_settings' ) );
	}

	/**
	 * Default option values.
	 *
	 * @return array
	 */
	public static function defaults() {
		return array(
			'page_slug'        => 'download',
			'auto_append'      => 1,
			'countdown'        => 10,
			'brand_name'       => 'ArabSeed Tech',
			'logo_url'         => 'https://www.arabseedtech.org/wp-content/uploads/2025/02/cropped-arabseed-tech-logo-450x69.webp',
			'default_url'      => home_url( '/' ),
			'primary_color'    => '#182B5C',
			'background_color' => '#FCF7EC',
			'button_text'      => 'تحميل',
			'alt_button_text'  => 'الرابط البديل !',
			'page_heading'     => 'جهزنا ملفك للتحميل',
			'page_subheading'  => 'شكراً لاختيارك المحتوى الحصري',
			'footer_text'      => 'ArabSeed Tech · جميع الحقوق محفوظة',
		);
	}

	/**
	 * Return all options merged with defaults.
	 *
	 * @return array
	 */
	public function all() {
		if ( null === $this->options ) {
			$stored        = get_option( self::OPTION_KEY, array() );
			$this->options = wp_parse_args( is_array( $stored ) ? $stored : array(), self::defaults() );
		}
		return $this->options;
	}

	/**
	 * Fetch a single option.
	 *
	 * @param string $key     Option key.
	 * @param mixed  $default Fallback.
	 * @return mixed
	 */
	public function get( $key, $default = '' ) {
		$all = $this->all();
		return isset( $all[ $key ] ) && '' !== $all[ $key ] ? $all[ $key ] : $default;
	}

	public function add_settings_page() {
		add_options_page(
			__( 'ArabSeed Download', 'arabseed-download-manager' ),
			__( 'ArabSeed Download', 'arabseed-download-manager' ),
			'manage_options',
			'asdm-settings',
			array( $this, 'render_settings_page' )
		);
	}

	public function register_settings() {
		register_setting(
			'asdm_settings_group',
			self::OPTION_KEY,
			array( $this, 'sanitize' )
		);
	}

	/**
	 * Sanitize submitted settings and flush rewrite rules if the slug changed.
	 *
	 * @param array $input Raw input.
	 * @return array
	 */
	public function sanitize( $input ) {
		$defaults = self::defaults();
		$old      = $this->all();
		$clean    = array();

		$slug                    = isset( $input['page_slug'] ) ? sanitize_title( $input['page_slug'] ) : '';
		$clean['page_slug']      = $slug ? $slug : $defaults['page_slug'];
		$clean['auto_append']    = empty( $input['auto_append'] ) ? 0 : 1;
		$clean['countdown']      = isset( $input['countdown'] ) ? max( 0, min( 60, absint( $input['countdown'] ) ) ) : $defaults['countdown'];
		$clean['brand_name']     = isset( $input['brand_name'] ) ? sanitize_text_field( $input['brand_name'] ) : $defaults['brand_name'];
		$clean['logo_url']       = isset( $input['logo_url'] ) ? esc_url_raw( $input['logo_url'] ) : $defaults['logo_url'];
		$clean['default_url']    = isset( $input['default_url'] ) ? esc_url_raw( $input['default_url'] ) : $defaults['default_url'];
		$clean['primary_color']  = $this->sanitize_hex( isset( $input['primary_color'] ) ? $input['primary_color'] : '', $defaults['primary_color'] );
		$clean['background_color'] = $this->sanitize_hex( isset( $input['background_color'] ) ? $input['background_color'] : '', $defaults['background_color'] );
		$clean['button_text']    = isset( $input['button_text'] ) ? sanitize_text_field( $input['button_text'] ) : $defaults['button_text'];
		$clean['alt_button_text'] = isset( $input['alt_button_text'] ) ? sanitize_text_field( $input['alt_button_text'] ) : $defaults['alt_button_text'];
		$clean['page_heading']   = isset( $input['page_heading'] ) ? sanitize_text_field( $input['page_heading'] ) : $defaults['page_heading'];
		$clean['page_subheading'] = isset( $input['page_subheading'] ) ? sanitize_text_field( $input['page_subheading'] ) : $defaults['page_subheading'];
		$clean['footer_text']    = isset( $input['footer_text'] ) ? sanitize_text_field( $input['footer_text'] ) : $defaults['footer_text'];

		// If the slug changed we must refresh rewrite rules.
		if ( ! isset( $old['page_slug'] ) || $old['page_slug'] !== $clean['page_slug'] ) {
			ASDM_Download_Page::instance()->register_rewrite_rules( $clean['page_slug'] );
			flush_rewrite_rules();
		}

		return $clean;
	}

	/**
	 * Validate a hex colour, falling back to a default.
	 *
	 * @param string $value    Candidate colour.
	 * @param string $fallback Default colour.
	 * @return string
	 */
	protected function sanitize_hex( $value, $fallback ) {
		$value = sanitize_hex_color( $value );
		return $value ? $value : $fallback;
	}

	public function render_settings_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$o        = $this->all();
		$page_url = home_url( '/' . $o['page_slug'] . '/' );
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'ArabSeed Download Manager', 'arabseed-download-manager' ); ?></h1>
			<p class="description">
				<?php esc_html_e( 'Set your brand and the look of the download page. Add the actual download link on each post using the "ArabSeed Download" box in the editor.', 'arabseed-download-manager' ); ?>
			</p>

			<div class="notice notice-info inline" style="margin:1rem 0;padding:.8rem 1rem;">
				<strong><?php esc_html_e( 'Your download page:', 'arabseed-download-manager' ); ?></strong>
				<a href="<?php echo esc_url( $page_url ); ?>" target="_blank" rel="noopener"><?php echo esc_html( $page_url ); ?></a><br>
				<strong><?php esc_html_e( 'Shortcode:', 'arabseed-download-manager' ); ?></strong>
				<code>[arabseed_download]</code>
				&mdash;
				<?php esc_html_e( 'or with an explicit link:', 'arabseed-download-manager' ); ?>
				<code>[arabseed_download url="https://datadock-host.site/f/XXXX"]</code>
			</div>

			<form method="post" action="options.php">
				<?php settings_fields( 'asdm_settings_group' ); ?>
				<table class="form-table" role="presentation">
					<tr>
						<th scope="row"><label for="asdm-brand"><?php esc_html_e( 'Brand name', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[brand_name]" id="asdm-brand" type="text" class="regular-text" value="<?php echo esc_attr( $o['brand_name'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-logo"><?php esc_html_e( 'Logo URL', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[logo_url]" id="asdm-logo" type="url" class="regular-text code" value="<?php echo esc_attr( $o['logo_url'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-slug"><?php esc_html_e( 'Download page slug', 'arabseed-download-manager' ); ?></label></th>
						<td>
							<code><?php echo esc_html( home_url( '/' ) ); ?></code>
							<input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[page_slug]" id="asdm-slug" type="text" class="regular-text" value="<?php echo esc_attr( $o['page_slug'] ); ?>" style="width:12rem">
							<code>/</code>
							<p class="description"><?php esc_html_e( 'The redesigned countdown page lives here. Visiting your Settings and saving refreshes the link automatically.', 'arabseed-download-manager' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><?php esc_html_e( 'Show button automatically', 'arabseed-download-manager' ); ?></th>
						<td>
							<label>
								<input type="checkbox" name="<?php echo esc_attr( self::OPTION_KEY ); ?>[auto_append]" value="1" <?php checked( 1, (int) $o['auto_append'] ); ?>>
								<?php esc_html_e( 'Add the download button at the end of every post that has a download link.', 'arabseed-download-manager' ); ?>
							</label>
							<p class="description"><?php esc_html_e( 'No shortcode needed. Turn this off if you prefer to place [arabseed_download] manually.', 'arabseed-download-manager' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-countdown"><?php esc_html_e( 'Countdown (seconds)', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[countdown]" id="asdm-countdown" type="number" min="0" max="60" value="<?php echo esc_attr( $o['countdown'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-default"><?php esc_html_e( 'Fallback URL', 'arabseed-download-manager' ); ?></label></th>
						<td>
							<input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[default_url]" id="asdm-default" type="url" class="regular-text code" value="<?php echo esc_attr( $o['default_url'] ); ?>">
							<p class="description"><?php esc_html_e( 'Where to send visitors if no download link was provided.', 'arabseed-download-manager' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><?php esc_html_e( 'Colours', 'arabseed-download-manager' ); ?></th>
						<td>
							<label><?php esc_html_e( 'Primary', 'arabseed-download-manager' ); ?>
								<input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[primary_color]" type="text" value="<?php echo esc_attr( $o['primary_color'] ); ?>" class="asdm-color" style="width:7rem">
							</label>
							&nbsp;&nbsp;
							<label><?php esc_html_e( 'Background', 'arabseed-download-manager' ); ?>
								<input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[background_color]" type="text" value="<?php echo esc_attr( $o['background_color'] ); ?>" class="asdm-color" style="width:7rem">
							</label>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-btn-text"><?php esc_html_e( 'Button text', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[button_text]" id="asdm-btn-text" type="text" class="regular-text" value="<?php echo esc_attr( $o['button_text'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-alt-text"><?php esc_html_e( 'Alternative link text', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[alt_button_text]" id="asdm-alt-text" type="text" class="regular-text" value="<?php echo esc_attr( $o['alt_button_text'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-heading"><?php esc_html_e( 'Page heading', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[page_heading]" id="asdm-heading" type="text" class="regular-text" value="<?php echo esc_attr( $o['page_heading'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-subheading"><?php esc_html_e( 'Page subheading', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[page_subheading]" id="asdm-subheading" type="text" class="regular-text" value="<?php echo esc_attr( $o['page_subheading'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="asdm-footer"><?php esc_html_e( 'Footer text', 'arabseed-download-manager' ); ?></label></th>
						<td><input name="<?php echo esc_attr( self::OPTION_KEY ); ?>[footer_text]" id="asdm-footer" type="text" class="regular-text" value="<?php echo esc_attr( $o['footer_text'] ); ?>"></td>
					</tr>
				</table>
				<?php submit_button(); ?>
			</form>
		</div>
		<?php
	}
}
