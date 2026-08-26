/**
 * ArabSeed download button — Gutenberg block (no build step).
 * A dynamic block: PHP renders the front end, the editor shows a simple
 * placeholder with link controls. Leave the link empty to use the post's
 * "ArabSeed Download" box value.
 */
(function (blocks, element, blockEditor, components, i18n) {
	'use strict';

	var el = element.createElement;
	var __ = i18n.__;
	var InspectorControls = blockEditor.InspectorControls;
	var PanelBody = components.PanelBody;
	var TextControl = components.TextControl;
	var SelectControl = components.SelectControl;

	blocks.registerBlockType('arabseed/download-button', {
		title: __('ArabSeed Download Button', 'arabseed-download-manager'),
		description: __('Insert the ArabSeed download button. Uses the post download link unless overridden here.', 'arabseed-download-manager'),
		icon: 'download',
		category: 'widgets',
		attributes: {
			url: { type: 'string', default: '' },
			altUrl: { type: 'string', default: '' },
			text: { type: 'string', default: '' },
			align: { type: 'string', default: 'center' }
		},
		edit: function (props) {
			var a = props.attributes;
			return el(
				'div',
				{ className: props.className },
				el(
					InspectorControls,
					{},
					el(
						PanelBody,
						{ title: __('Download settings', 'arabseed-download-manager'), initialOpen: true },
						el(TextControl, {
							label: __('Download link (optional)', 'arabseed-download-manager'),
							help: __('Leave empty to use the post’s ArabSeed Download box.', 'arabseed-download-manager'),
							value: a.url,
							onChange: function (v) { props.setAttributes({ url: v }); }
						}),
						el(TextControl, {
							label: __('Alternative link (optional)', 'arabseed-download-manager'),
							value: a.altUrl,
							onChange: function (v) { props.setAttributes({ altUrl: v }); }
						}),
						el(TextControl, {
							label: __('Button text (optional)', 'arabseed-download-manager'),
							value: a.text,
							onChange: function (v) { props.setAttributes({ text: v }); }
						}),
						el(SelectControl, {
							label: __('Alignment', 'arabseed-download-manager'),
							value: a.align,
							options: [
								{ label: __('Center', 'arabseed-download-manager'), value: 'center' },
								{ label: __('Start', 'arabseed-download-manager'), value: 'right' },
								{ label: __('End', 'arabseed-download-manager'), value: 'left' }
							],
							onChange: function (v) { props.setAttributes({ align: v }); }
						})
					)
				),
				el(
					'div',
					{
						style: {
							textAlign: 'center',
							padding: '1rem',
							border: '1px dashed #182B5C',
							borderRadius: '14px',
							color: '#182B5C',
							fontWeight: 600
						}
					},
					el('span', { className: 'dashicons dashicons-download', style: { marginInlineEnd: '6px' } }),
					__('ArabSeed Download Button', 'arabseed-download-manager'),
					a.url ? el('div', { style: { fontWeight: 400, fontSize: '12px', marginTop: '4px', wordBreak: 'break-all' } }, a.url) : null
				)
			);
		},
		save: function () {
			return null; // Dynamic block rendered by PHP.
		}
	});
})(
	window.wp.blocks,
	window.wp.element,
	window.wp.blockEditor,
	window.wp.components,
	window.wp.i18n
);
