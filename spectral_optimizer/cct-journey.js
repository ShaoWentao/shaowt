(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    root.CctJourney = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function injectChromaticityLayoutFix() {
        if (typeof document === 'undefined' || document.getElementById('chromaticity-layout-fix')) return;
        const style = document.createElement('style');
        style.id = 'chromaticity-layout-fix';
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
                align-items: start;
                height: auto;
                min-height: 0;
                max-height: none;
                overflow: visible;
            }

            .controls-panel {
                position: static;
                top: auto;
                max-height: none;
                overflow: visible;
                align-self: start;
            }

            .visualization-area {
                min-width: 0;
                height: auto;
                min-height: 0;
                max-height: none;
                overflow: visible;
                align-self: start;
            }

            .charts-row {
                display: grid;
                grid-template-columns: minmax(0, 1.65fr) minmax(300px, 0.85fr);
                gap: 18px;
                align-items: start;
            }

            .spd-panel,
            .cie-panel {
                min-width: 0;
                height: auto;
                align-self: start;
                padding: 18px;
                overflow: hidden;
            }

            .canvas-wrapper {
                position: relative;
                width: 100%;
                min-width: 0;
                overflow: hidden;
            }

            #canvas-wrapper {
                width: 100%;
                height: auto;
                aspect-ratio: 16 / 10;
                min-height: 0;
                max-height: none;
            }

            #cie-canvas-wrapper {
                width: 100%;
                height: auto;
                aspect-ratio: 1 / 1;
                min-height: 0;
                max-height: none;
            }

            #spd-canvas,
            #cie-canvas {
                display: block;
                width: 100%;
                height: 100%;
            }

            @media (max-width: 1100px) {
                .charts-row {
                    grid-template-columns: minmax(0, 1fr);
                }

                .cie-panel {
                    width: 100%;
                    max-width: 680px;
                    justify-self: center;
                }
            }

            @media (max-width: 640px) {
                .spd-panel,
                .cie-panel {
                    padding: 14px;
                }

                #canvas-wrapper {
                    aspect-ratio: 16 / 10;
                }
            }
        `;
        document.head.appendChild(style);
    }

    injectChromaticityLayoutFix();

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