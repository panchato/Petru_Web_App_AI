(function (global) {
    'use strict';

    const defaultIds = Object.freeze({
        extraLight: 'extra_light',
        light: 'light',
        lightAmber: 'light_amber',
        amber: 'amber',
        lessThan30: 'lessthan30',
        between3032: 'between3032',
        between3234: 'between3234',
        between3436: 'between3436',
        moreThan36: 'morethan36',
        units: 'units',
        inshellWeight: 'inshell_weight',
        shelledWeight: 'shelled_weight',
        yieldPercentage: 'yieldpercentage'
    });

    function getElement(id) {
        return document.getElementById(id);
    }

    function parseFloatOrNaN(value) {
        return parseFloat(value);
    }

    function parseIntOrZero(value) {
        return parseInt(value, 10) || 0;
    }

    function resolveIds(ids) {
        return {
            ...defaultIds,
            ...(ids || {})
        };
    }

    function bind({ ids } = {}) {
        const resolved = resolveIds(ids);

        const elements = {
            extraLight: getElement(resolved.extraLight),
            light: getElement(resolved.light),
            lightAmber: getElement(resolved.lightAmber),
            amber: getElement(resolved.amber),
            lessThan30: getElement(resolved.lessThan30),
            between3032: getElement(resolved.between3032),
            between3234: getElement(resolved.between3234),
            between3436: getElement(resolved.between3436),
            moreThan36: getElement(resolved.moreThan36),
            units: getElement(resolved.units),
            inshellWeight: getElement(resolved.inshellWeight),
            shelledWeight: getElement(resolved.shelledWeight),
            yieldPercentage: getElement(resolved.yieldPercentage)
        };

        if (
            !elements.extraLight ||
            !elements.light ||
            !elements.lightAmber ||
            !elements.amber ||
            !elements.lessThan30 ||
            !elements.between3032 ||
            !elements.between3234 ||
            !elements.between3436 ||
            !elements.moreThan36 ||
            !elements.units ||
            !elements.inshellWeight ||
            !elements.shelledWeight ||
            !elements.yieldPercentage
        ) {
            return;
        }

        const updateShelledWeight = () => {
            const extraLight = parseFloatOrNaN(elements.extraLight.value) || 0;
            const light = parseFloatOrNaN(elements.light.value) || 0;
            const lightAmber = parseFloatOrNaN(elements.lightAmber.value) || 0;
            const amber = parseFloatOrNaN(elements.amber.value) || 0;
            const total = extraLight + light + lightAmber + amber;

            if (total > 0) {
                elements.shelledWeight.value = total.toFixed(2);
            } else {
                elements.shelledWeight.value = '';
            }
        };

        const updateYieldPercentage = () => {
            const inshell = parseFloatOrNaN(elements.inshellWeight.value);
            const shelled = parseFloatOrNaN(elements.shelledWeight.value);
            if (!Number.isNaN(inshell) && inshell > 0 && !Number.isNaN(shelled)) {
                const yieldPct = (shelled / inshell) * 100;
                elements.yieldPercentage.value = yieldPct.toFixed(2);
            } else {
                elements.yieldPercentage.value = '';
            }
        };

        const formatYieldPercentage = () => {
            const current = parseFloatOrNaN(elements.yieldPercentage.value);
            if (!Number.isNaN(current)) {
                elements.yieldPercentage.value = current.toFixed(2);
            }
        };

        const updateUnits = () => {
            const less30 = parseIntOrZero(elements.lessThan30.value);
            const between3032 = parseIntOrZero(elements.between3032.value);
            const between3234 = parseIntOrZero(elements.between3234.value);
            const between3436 = parseIntOrZero(elements.between3436.value);
            const morethan36 = parseIntOrZero(elements.moreThan36.value);
            const totalUnits = less30 + between3032 + between3234 + between3436 + morethan36;
            elements.units.value = totalUnits;
        };

        const colorInputs = [elements.extraLight, elements.light, elements.lightAmber, elements.amber];
        colorInputs.forEach((input) => {
            input.addEventListener('change', () => {
                updateShelledWeight();
                updateYieldPercentage();
            });
        });

        const sizeInputs = [
            elements.lessThan30,
            elements.between3032,
            elements.between3234,
            elements.between3436,
            elements.moreThan36
        ];
        sizeInputs.forEach((input) => {
            input.addEventListener('change', updateUnits);
        });

        elements.inshellWeight.addEventListener('change', updateYieldPercentage);

        updateShelledWeight();
        updateUnits();
        formatYieldPercentage();
    }

    global.QCCalculator = Object.freeze({
        bind
    });
})(window);
