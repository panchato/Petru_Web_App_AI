(function (global) {
    'use strict';

    function bind(searchInputId, selectId) {
        const search = document.getElementById(searchInputId);
        const select = document.getElementById(selectId);
        if (!search || !select) {
            return;
        }

        const originalOptions = Array.from(select.options).map((option) => ({
            value: option.value,
            text: option.text,
            selected: option.selected
        }));

        const render = (filterText) => {
            const selectedValue = select.value;
            const normalized = (filterText || '').toLowerCase().trim();
            const nextOptions = [];

            for (const item of originalOptions) {
                if (!normalized || item.text.toLowerCase().includes(normalized)) {
                    const option = document.createElement('option');
                    option.value = item.value;
                    option.text = item.text;
                    option.selected = item.value === selectedValue || (item.selected && !selectedValue);
                    nextOptions.push(option);
                }
            }

            select.replaceChildren(...nextOptions);
        };

        search.addEventListener('input', () => {
            render(search.value);
        });
    }

    function bindMany(bindings) {
        if (!Array.isArray(bindings)) {
            return;
        }

        for (const binding of bindings) {
            if (!binding || !binding.searchInputId || !binding.selectId) {
                continue;
            }
            bind(binding.searchInputId, binding.selectId);
        }
    }

    global.SearchableSelect = Object.freeze({
        bind,
        bindMany
    });
})(window);
