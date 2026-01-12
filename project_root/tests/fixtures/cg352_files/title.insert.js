(() => {
    let element = document.head;

    fetch('includes/title.insert.html').then(data => data.text()).then(data => {
        element.innerHTML += data
    })
})();