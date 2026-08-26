<?php
/**
 * Redesigned download page. Standalone document (it does not load the theme so
 * it stays fast and distraction-free). The countdown -> reveal -> redirect
 * logic is unchanged from the original index.html.
 *
 * @package ArabSeed_Download_Manager
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$asdm = get_query_var( 'asdm_config' );
if ( ! is_array( $asdm ) ) {
	$asdm = array();
}

$primary    = isset( $asdm['primaryColor'] ) ? $asdm['primaryColor'] : '#182B5C';
$background  = isset( $asdm['backgroundColor'] ) ? $asdm['backgroundColor'] : '#FCF7EC';
$brand      = isset( $asdm['brandName'] ) ? $asdm['brandName'] : 'ArabSeed Tech';
$logo       = isset( $asdm['logoUrl'] ) ? $asdm['logoUrl'] : '';
$heading    = isset( $asdm['heading'] ) ? $asdm['heading'] : '';
$subheading = isset( $asdm['subheading'] ) ? $asdm['subheading'] : '';
$footer     = isset( $asdm['footerText'] ) ? $asdm['footerText'] : '';
$year       = isset( $asdm['year'] ) ? $asdm['year'] : gmdate( 'Y' );

// Inline colour tokens so the design tracks the admin settings.
$style_vars = sprintf(
	'--asdm-primary:%1$s;--asdm-bg:%2$s;',
	esc_attr( $primary ),
	esc_attr( $background )
);
?>
<!DOCTYPE html>
<html <?php language_attributes(); ?> dir="rtl">
<head>
	<meta charset="<?php bloginfo( 'charset' ); ?>">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<meta name="robots" content="noindex, nofollow">
	<meta name="referrer" content="no-referrer-when-downgrade">
	<title><?php echo esc_html( sprintf( '%1$s · %2$s', __( 'تجهيز التحميل', 'arabseed-download-manager' ), $brand ) ); ?></title>
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
	<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap">
	<link rel="stylesheet" href="<?php echo esc_url( ASDM_URL . 'assets/css/asdm-download-page.css?v=' . ASDM_VERSION ); ?>">
	<?php if ( $logo ) : ?>
	<link rel="icon" href="<?php echo esc_url( $logo ); ?>">
	<?php endif; ?>
	<script>
		window.ASDM = <?php echo wp_json_encode( $asdm ); ?>;
	</script>
</head>
<body style="<?php echo esc_attr( $style_vars ); ?>">
	<main class="asdm-card" role="main">
		<div class="asdm-brand<?php echo $logo ? ' asdm-brand--logo' : ''; ?>">
			<?php if ( $logo ) : ?>
			<img class="asdm-brand__img" src="<?php echo esc_url( $logo ); ?>" alt="<?php echo esc_attr( $brand ); ?>">
			<?php else : ?>
			<span class="asdm-brand__name"><?php echo esc_html( $brand ); ?></span>
			<?php endif; ?>
		</div>

		<h1 class="asdm-heading">
			<span class="asdm-heading__icon" aria-hidden="true">
				<svg viewBox="0 0 24 24" width="26" height="26"><path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v9.586l2.293-2.293a1 1 0 0 1 1.414 1.414l-4 4a1 1 0 0 1-1.414 0l-4-4a1 1 0 1 1 1.414-1.414L11 13.586V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v1h12v-1a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z"/></svg>
			</span>
			<?php echo esc_html( $heading ); ?>
		</h1>

		<?php if ( $subheading ) : ?>
		<p class="asdm-subheading"><?php echo esc_html( $subheading ); ?></p>
		<?php endif; ?>

		<figure class="asdm-feature is-hidden" id="asdm-feature-wrap">
			<img id="asdm-feature" src="" alt="">
		</figure>

		<p class="asdm-file is-hidden" id="asdm-file">
			<span class="asdm-file__label"><?php esc_html_e( 'الملف', 'arabseed-download-manager' ); ?>:</span>
			<span class="asdm-file__name" id="asdm-file-name"></span>
		</p>

		<div class="asdm-timer" data-state="counting">
			<div class="asdm-ring">
				<svg class="asdm-ring__svg" viewBox="0 0 170 170" aria-hidden="true">
					<circle class="asdm-ring__bg" cx="85" cy="85" r="71"></circle>
					<circle class="asdm-ring__fill" id="asdm-progress" cx="85" cy="85" r="71"></circle>
				</svg>
				<div class="asdm-ring__value">
					<span id="asdm-count">10</span>
					<small><?php esc_html_e( 'ثانية', 'arabseed-download-manager' ); ?></small>
				</div>
			</div>
			<p class="asdm-status" id="asdm-status" aria-live="polite">
				<?php esc_html_e( 'جاري تجهيز الرابط ...', 'arabseed-download-manager' ); ?>
			</p>
		</div>

		<a class="asdm-download-btn is-hidden" id="asdm-download" href="#" rel="nofollow noopener">
			<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v9.586l2.293-2.293a1 1 0 0 1 1.414 1.414l-4 4a1 1 0 0 1-1.414 0l-4-4a1 1 0 1 1 1.414-1.414L11 13.586V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v1h12v-1a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z"/></svg>
			<span><?php esc_html_e( 'انقر للتحميل الآن', 'arabseed-download-manager' ); ?></span>
		</a>

		<section class="asdm-steps" aria-label="<?php esc_attr_e( 'خطوات التحميل', 'arabseed-download-manager' ); ?>">
			<h2 class="asdm-steps__title"><?php esc_html_e( 'خطوات سريعة', 'arabseed-download-manager' ); ?></h2>
			<ol class="asdm-steps__list">
				<li><span class="asdm-steps__num">١</span><?php esc_html_e( 'انتظر انتهاء العدّاد', 'arabseed-download-manager' ); ?></li>
				<li><span class="asdm-steps__num">٢</span><?php esc_html_e( 'اضغط زر التحميل', 'arabseed-download-manager' ); ?></li>
				<li><span class="asdm-steps__num">٣</span><?php esc_html_e( 'احفظ الملف بجهازك', 'arabseed-download-manager' ); ?></li>
			</ol>
		</section>

		<footer class="asdm-footer">
			&copy; <?php echo esc_html( $year . ' · ' . $footer ); ?>
		</footer>
	</main>

	<script src="<?php echo esc_url( ASDM_URL . 'assets/js/asdm-download-page.js?v=' . ASDM_VERSION ); ?>"></script>
</body>
</html>
