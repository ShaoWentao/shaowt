(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    root.CctJourney = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function injectLayoutFix() {
        if (typeof document === 'undefined' || document.getElementById('spectral-layout-fix')) return;
        const style = document.createElement('style');
        style.id = 'spectral-layout-fix';
        style.textContent = `
            html,
            body {
                width: 100%;
                height: auto;
                min-height: 100%;
                overflow-x: hidden;
                overflow-y: auto !important;
                overscroll-behavior-y: auto;
            }

            body {
                position: static;
                touch-action: pan-y;
            }

            #app-main {
                height: auto;
                min-height: 0;
                max-height: none;
                overflow: visible;
                align-items: start;
                grid-auto-rows: max-content;
            }

            .visualization-area {
                height: auto;
                min-height: 0;
                max-height: none;
                overflow: visible;
                align-self: start;
            }

            .controls-panel {
                position: static;
                top: auto;
                max-height: none;
                overflow: visible;
                align-self: start;
            }

            .visualization-area,
            .charts-row,
            .spd-panel,
            .cie-panel {
                min-width: 0;
            }

            .charts-row {
                display: grid;
                grid-template-columns: minmax(0, 1.65fr) minmax(300px, 1fr);
                gap: 18px;
                align-items: start;
                grid-auto-rows: max-content;
            }

            .spd-panel,
            .cie-panel {
                overflow: hidden;
                align-self: start;
                height: auto;
            }

            .canvas-wrapper {
                width: 100%;
                min-width: 0;
            }

            #cie-canvas-wrapper {
                width: 100%;
                aspect-ratio: 1 / 1;
                height: auto;
                max-height: none;
            }

            #spd-canvas,
            #cie-canvas {
                display: block;
                width: 100%;
                height: 100%;
            }

            .presets-toggle {
                width: 100%;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                padding: 0;
                border: 0;
                background: transparent;
                color: var(--text-secondary);
                font: inherit;
                cursor: pointer;
                text-align: left;
            }

            .presets-toggle strong {
                color: var(--text-secondary);
                font-size: 0.82rem;
                font-weight: 600;
            }

            .presets-toggle strong span {
                font-size: 0.72rem;
                font-weight: 400;
                color: var(--text-muted);
                margin-left: 4px;
            }

            .presets-toggle-icon {
                font-size: 0.9rem;
                line-height: 1;
                transition: transform 0.2s ease;
            }

            .presets-toggle[aria-expanded="true"] .presets-toggle-icon {
                transform: rotate(180deg);
            }

            .presets-section .preset-buttons[hidden] {
                display: none !important;
            }

            .presets-section .preset-buttons:not([hidden]) {
                margin-top: 10px;
            }

            @media (max-width: 1180px) {
                .charts-row {
                    grid-template-columns: 1fr;
                }

                .cie-panel {
                    width: min(100%, 680px);
                    justify-self: center;
                }
            }
        `;
        document.head.appendChild(style);
    }

    function initPresetCollapse() {
        if (typeof document === 'undefined') return;
        const section = document.querySelector('.presets-section');
        const buttons = section && section.querySelector('.preset-buttons');
        const heading = section && section.querySelector('h3');
        if (!section || !buttons || !heading || section.querySelector('.presets-toggle')) return;

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'presets-toggle';
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-controls', 'preset-buttons');
        toggle.innerHTML = '<strong>快速预设 <span>Presets</span></strong><span class="presets-toggle-icon" aria-hidden="true">⌄</span>';

        buttons.id = 'preset-buttons';
        buttons.hidden = true;
        heading.replaceWith(toggle);

        toggle.addEventListener('click', function () {
            const expanded = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', String(!expanded));
            buttons.hidden = expanded;
        });
    }

    injectLayoutFix();
    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initPresetCollapse, { once: true });
        } else {
            initPresetCollapse();
        }
    }

    function freezeScene(scene) {
        return Object.freeze(scene);
    }

    const HUMAN_CENTRED_SCENES = Object.freeze([
        freezeScene({
            id: 'morning-transition',
            labelZh: '\u6668\u95f4\u8fc7\u6e21',
            labelEn: 'Morning Transition',
            cctK: 3500,
            duv: 0,
            illuminanceLux: 250,
            emphasis: 'moderate-daytime-circadian-support'
        }),
        freezeScene({
            id: 'daytime-focus',
            labelZh: '\u65e5\u95f4\u4e13\u6ce8',
            labelEn: 'Daytime Focus',
            cctK: 5000,
            duv: 0,
            illuminanceLux: 400,
            emphasis: 'higher-daytime-melanopic-and-cla2-response'
        }),
        freezeScene({
            id: 'collaboration',
            labelZh: '\u534f\u4f5c\u4ea4\u6d41',
            labelEn: 'Collaboration',
            cctK: 4000,
            duv: 0,
            illuminanceLux: 300,
            emphasis: 'balanced-facial-appearance-colour-fidelity-and-circadian-support'
        }),
        freezeScene({
            id: 'colour-vitality',
            labelZh: '\u8272\u5f69\u6d3b\u529b',
            labelEn: 'Colour Vitality',
            cctK: 3500,
            duv: 0,
            illuminanceLux: 300,
            emphasis: 'high-fidelity-and-rg-105-115'
        }),
        freezeScene({
            id: 'evening-wind-down',
            labelZh: '\u591c\u95f4\u653e\u677e',
            labelEn: 'Evening Wind-down',
            cctK: 2700,
            duv: 0,
            illuminanceLux: 75,
            emphasis: 'lower-melanopic-and-cla2-stimulus'
        }),
        freezeScene({
            id: 'night-low-disturbance',
            labelZh: '\u591c\u95f4\u4f4e\u5e72\u6270',
            labelEn: 'Night Low Disturbance',
            cctK: 2000,
            duv: 0,
            illuminanceLux: 10,
            emphasis: 'minimize-melanopic-and-cla2-stimulus'
        })
    ]);

    function buildCctJourney() {
        const ascending = [1600];
        for (let cctK = 2000; cctK <= 12000; cctK += 500) ascending.push(cctK);
        return ascending.concat(ascending.slice(0, -1).reverse());
    }

    function sceneById(id) {
        if (typeof id !== 'string') return null;
        return HUMAN_CENTRED_SCENES.find(function (scene) {
            return scene.id === id;
        }) || null;
    }

    return {
        buildCctJourney,
        HUMAN_CENTRED_SCENES,
        sceneById
    };
});