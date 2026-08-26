<?php
/**
 * "ArabSeed Download" meta box: lets an author paste the download link (and an
 * optional alternative link + feature image) straight into the post editor.
 *
 * @package ArabSeed_Download_Manager
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class ASDM_Metabox {

	const NONCE      = 'asdm_metabox_nonce';
	const META_URL   = '_asdm_download_url';
	const META_ALT   = '_asdm_alt_url';
	const META_TEXT  = '_asdm_button_text';
	const META_IMAGE = '_asdm_feature_image';
	const META_FILE  = '_asdm_file_name';

	protected static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	protected function __construct() {
		add_action( 'add_meta_boxes', array( $this, 'add_meta_box' ) );
		add_action( 'save_post', array( $this, 'save' ), 10, 2 );
	}

	/**
	 * Post types the box appears on.
	 *
	 * @return array
	 */
	protected function post_types() {
		return apply_filters( 'asdm_metabox_post_types', array( 'post', 'page' ) );
	}

	public function add_meta_box() {
		foreach ( $this->post_types() as $type ) {
			add_meta_box(
				'asdm_download_box',
				__( 'ArabSeed Download', 'arabseed-download-manager' ),
				array( $this, 'render' ),
				$type,
				'side',
				'high'
			);
		}
	}

	/**
	 * Render the meta box UI.
	 *
	 * @param WP_Post $post Current post.
	 */
	public function render( $post ) {
		wp_nonce_field( 'asdm_save_meta', self::NONCE );

		$url   = get_post_meta( $post->ID, self::META_URL, true );
		$alt   = get_post_meta( $post->ID, self::META_ALT, true );
		$text  = get_post_meta( $post->ID, self::META_TEXT, true );
		$image = get_post_meta( $post->ID, self::META_IMAGE, true );
		$file  = get_post_meta( $post->ID, self::META_FILE, true );
		?>
		<p>
			<label for="asdm-url"><strong><?php esc_html_e( 'Download link', 'arabseed-download-manager' ); ?></strong></label>
			<input type="url" id="asdm-url" name="asdm_download_url" class="widefat" placeholder="https://datadock-host.site/f/XXXX" value="<?php echo esc_attr( $url ); ?>">
			<span class="description"><?php esc_html_e( 'The real file link the button leads to.', 'arabseed-download-manager' ); ?></span>
		</p>
		<p>
			<label for="asdm-alt"><strong><?php esc_html_e( 'Alternative link (optional)', 'arabseed-download-manager' ); ?></strong></label>
			<input type="url" id="asdm-alt" name="asdm_alt_url" class="widefat" placeholder="https://..." value="<?php echo esc_attr( $alt ); ?>">
		</p>
		<p>
			<label for="asdm-file"><strong><?php esc_html_e( 'File name / title (optional)', 'arabseed-download-manager' ); ?></strong></label>
			<input type="text" id="asdm-file" name="asdm_file_name" class="widefat" value="<?php echo esc_attr( $file ); ?>">
		</p>
		<p>
			<label for="asdm-image"><strong><?php esc_html_e( 'Feature image URL (optional)', 'arabseed-download-manager' ); ?></strong></label>
			<input type="url" id="asdm-image" name="asdm_feature_image" class="widefat" placeholder="https://..." value="<?php echo esc_attr( $image ); ?>">
			<span class="description"><?php esc_html_e( 'Shown on the download page. Falls back to the post thumbnail.', 'arabseed-download-manager' ); ?></span>
		</p>
		<p>
			<label for="asdm-text"><strong><?php esc_html_e( 'Button text (optional)', 'arabseed-download-manager' ); ?></strong></label>
			<input type="text" id="asdm-text" name="asdm_button_text" class="widefat" value="<?php echo esc_attr( $text ); ?>">
		</p>
		<p class="description">
			<?php esc_html_e( 'Place the button in your content with:', 'arabseed-download-manager' ); ?><br>
			<code>[arabseed_download]</code>
		</p>
		<?php
	}

	/**
	 * Persist the fields.
	 *
	 * @param int     $post_id Post ID.
	 * @param WP_Post $post    Post object.
	 */
	public function save( $post_id, $post ) {
		if ( ! isset( $_POST[ self::NONCE ] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST[ self::NONCE ] ) ), 'asdm_save_meta' ) ) {
			return;
		}
		if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
			return;
		}
		if ( ! current_user_can( 'edit_post', $post_id ) ) {
			return;
		}
		if ( ! in_array( $post->post_type, $this->post_types(), true ) ) {
			return;
		}

		$fields = array(
			self::META_URL   => isset( $_POST['asdm_download_url'] ) ? esc_url_raw( wp_unslash( $_POST['asdm_download_url'] ) ) : '',
			self::META_ALT   => isset( $_POST['asdm_alt_url'] ) ? esc_url_raw( wp_unslash( $_POST['asdm_alt_url'] ) ) : '',
			self::META_IMAGE => isset( $_POST['asdm_feature_image'] ) ? esc_url_raw( wp_unslash( $_POST['asdm_feature_image'] ) ) : '',
			self::META_TEXT  => isset( $_POST['asdm_button_text'] ) ? sanitize_text_field( wp_unslash( $_POST['asdm_button_text'] ) ) : '',
			self::META_FILE  => isset( $_POST['asdm_file_name'] ) ? sanitize_text_field( wp_unslash( $_POST['asdm_file_name'] ) ) : '',
		);

		foreach ( $fields as $key => $value ) {
			if ( '' === $value ) {
				delete_post_meta( $post_id, $key );
			} else {
				update_post_meta( $post_id, $key, $value );
			}
		}
	}
}
