(function (global) {
    'use strict';

    function toNumber(value) {
        const number = Number(value);
        return Number.isFinite(number) ? number : 0;
    }

    function createFormatter(locale) {
        return new Intl.NumberFormat(locale || 'es-CL', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function calculateNet(loaded, empty, tare, quantity) {
        return loaded - empty - (tare * quantity);
    }

    function bindSingle({ loadedInputId, emptyInputId, previewId, tare, quantity, locale }) {
        const loadedInput = document.getElementById(loadedInputId);
        const emptyInput = document.getElementById(emptyInputId);
        const preview = document.getElementById(previewId);
        if (!loadedInput || !emptyInput || !preview) {
            return;
        }

        const tareValue = toNumber(tare);
        const quantityValue = toNumber(quantity);
        const formatter = createFormatter(locale);

        const refreshPreview = () => {
            const loaded = toNumber(loadedInput.value || 0);
            const empty = toNumber(emptyInput.value || 0);
            const net = calculateNet(loaded, empty, tareValue, quantityValue);
            preview.textContent = `${formatter.format(net)} kg`;
        };

        loadedInput.addEventListener('input', refreshPreview);
        emptyInput.addEventListener('input', refreshPreview);
        refreshPreview();
    }

    function bindInlineForms({ formSelector, loadedSelector, emptySelector, previewSelector, locale }) {
        const forms = document.querySelectorAll(formSelector);
        if (!forms.length) {
            return;
        }

        const formatter = createFormatter(locale);

        forms.forEach((form) => {
            const loaded = form.querySelector(loadedSelector);
            const empty = form.querySelector(emptySelector);
            const preview = form.querySelector(previewSelector);
            if (!loaded || !empty || !preview) {
                return;
            }

            const refresh = () => {
                const tare = toNumber(preview.dataset.tare || 0);
                const quantity = toNumber(preview.dataset.quantity || 0);
                const loadedValue = toNumber(loaded.value || 0);
                const emptyValue = toNumber(empty.value || 0);
                const net = calculateNet(loadedValue, emptyValue, tare, quantity);
                preview.textContent = `Neto: ${formatter.format(net)} kg`;
            };

            loaded.addEventListener('input', refresh);
            empty.addEventListener('input', refresh);
            refresh();
        });
    }

    global.WeightPreview = Object.freeze({
        bindSingle,
        bindInlineForms
    });
})(window);
