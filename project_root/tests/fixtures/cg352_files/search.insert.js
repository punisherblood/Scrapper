(() => {
    let element = document.body;
    let header = document.getElementsByTagName('header');

    fetch('includes/search.insert.html').then(data => data.text()).then(data => {
		let node = document.createElement('div');
		node.classList.add('search')
		node.innerHTML = data;
        header[0].after(node)
        search_init();
    })

    function search_init() {
        const search_input = _id('search-input');
        const search_stats = _id('search-stats');

        _id('search-prev').addEventListener('click', focus_search_prev)
        _id('search-next').addEventListener('click', focus_search_next)

        if (!search_input) {
            return;
        }

        search_input.addEventListener('input', () => {
            let value = search_input.value;

            if (value == null || value.length < 1) {
                return;
            }

            let setting_result = XPathResult.ORDERED_NODE_ITERATOR_TYPE;
            let result = document.evaluate(`//*[contains(text(), '${value}')]`, document, null, setting_result, null);

            search_key = 0;
            search_elements.splice(0, search_elements.length);


            if (!result) {
                search_stats.style.visibility = 'hidden'
                return;
            }

            let node;

            while ((node = result.iterateNext())) {
                search_elements.push(node);
            }

            if (search_elements.length < 1) {
                search_stats.style.visibility = 'hidden'
                return;
            }

            focus_search_item();
        })
    }

    function focus_search_prev() {
        search_key = Math.min(Math.max(search_key - 1, 0), search_elements.length);
        focus_search_item();
    }

    function focus_search_next() {
        search_key = Math.min(Math.max(search_key + 1, 0), search_elements.length);
        focus_search_item();
    }

    function focus_search_item() {

        const searcher = _id('searcher');
        const search_count = _id('search-count');
        const search_pos = _id('search-pos');

        let node = search_elements[search_key];

        if (!node) {
            return;
        }

        scrollIntoViewWithOffset(node, searcher.offsetHeight + 15);

        const search_stats = _id('search-stats');
        search_stats.style.visibility = ''
        search_count.innerText = `${search_elements.length}`;
        search_pos.innerText = `[${search_key + 1} / ${search_elements.length}]`;
    }

    const scrollIntoViewWithOffset = (selector, offset) => {
        window.scrollTo({
            behavior: 'smooth',
            top:
                selector.getBoundingClientRect().top -
                document.body.getBoundingClientRect().top -
                offset,
        })
    }
})();