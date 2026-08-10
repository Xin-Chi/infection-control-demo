/*
 * Shared front-end helpers.
 *
 * The original pages turned CSRF protection off server-side (`@csrf_exempt`)
 * so their AJAX calls would go through.  Here the token is read from the
 * cookie and sent with every unsafe request, and the views stay protected.
 */
(function (window, document) {
    'use strict';

    function getCookie(name) {
        const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return match ? decodeURIComponent(match.pop()) : '';
    }

    /** POST form-encoded data and resolve with the parsed JSON body. */
    async function postJSON(url, data) {
        const body = new URLSearchParams();
        Object.entries(data || {}).forEach(([key, value]) => {
            if (Array.isArray(value)) {
                value.forEach((item) => body.append(key, item));
            } else if (value !== undefined && value !== null) {
                body.append(key, value);
            }
        });

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body,
            credentials: 'same-origin',
        });
        return handle(response);
    }

    /** GET and resolve with the parsed JSON body. */
    async function getJSON(url, params) {
        const query = new URLSearchParams(params || {}).toString();
        const response = await fetch(query ? `${url}?${query}` : url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        });
        return handle(response);
    }

    async function handle(response) {
        let payload = null;
        try {
            payload = await response.json();
        } catch (err) {
            payload = null;
        }
        if (!response.ok) {
            const message = (payload && payload.error) || `HTTP ${response.status}`;
            throw new Error(message);
        }
        return payload;
    }

    /**
     * Set text content from untrusted data.
     *
     * Values coming back from the API are written with textContent rather than
     * innerHTML, so a term or patient name containing markup is displayed
     * literally instead of being parsed as HTML.
     */
    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined && text !== null) {
            node.textContent = String(text);
        }
        return node;
    }

    function clear(node) {
        while (node && node.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function showEmpty(node, message) {
        clear(node);
        node.appendChild(el('div', 'empty-state', message));
    }

    /** Wire a drawer toggle button to its panel. */
    function bindDrawer(toggleId, drawerId) {
        const toggle = document.getElementById(toggleId);
        const drawer = document.getElementById(drawerId);
        if (!toggle || !drawer) {
            return;
        }
        toggle.addEventListener('click', () => drawer.classList.toggle('is-open'));
        const close = drawer.querySelector('.drawer__close');
        if (close) {
            close.addEventListener('click', () => drawer.classList.remove('is-open'));
        }
    }

    window.App = { getJSON, postJSON, el, clear, showEmpty, bindDrawer };
})(window, document);
