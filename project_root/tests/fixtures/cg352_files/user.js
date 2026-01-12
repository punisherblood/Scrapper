/**
 * Получение элемента по ID
 * @param e
 * @returns {HTMLElement}
 * @private
 */
const _id = (e) => document.getElementById(e);

/**
 * Получение элемента по тегу
 * @param e
 * @returns {HTMLCollectionOf<HTMLElementTagNameMap[keyof HTMLElementTagNameMap]>}
 * @private
 */
const _tag = (e) => document.getElementsByTagName(e);

/**
 * Получение элемента по класс нейму
 * @param e
 * @returns {HTMLCollectionOf<HTMLElementTagNameMap[keyof HTMLElementTagNameMap]>}
 * @private
 */
const _class = (e) => document.getElementsByClassName(e);

/**
 * Создание элемента
 * @param e
 * @returns { HTMLElement }
 * @private
 */
const _create = (e) => document.createElement(e);

/**
 * Удаление аттрибута элемента
 * @param e
 * @param a
 * @private
 */
const _remove_attr = (e, a) => e.removeAttribute(a);

/**
 * Найденные совпадения
 * @type {*[]}
 */
const search_elements = [];

/**
 * Ключ поиска
 * @type {number}
 */
let search_key = 0;

/**
 * Фикс таблицы
 */
function fix_table() {
    const table = _class('output-table');

    if (!table) {
        return;
    }

    [...table].forEach(e => {
        fix_table_item(e)
    })
}

/**
 * Фикс элемента таблицы
 * @param table
 */
function fix_table_item(table) {
    const thead = _create('thead');
    const tbody = table;

    table.appendChild(thead);

    if (!tbody.children[0]) {
        return;
    }

    const firstChild = tbody.children[0].firstChild;

    if (!firstChild) {
        return;
    }

    thead.appendChild(firstChild);
}

/**
 * Соединение ячеек
 * @param table
 */
function mergeEmptyCellsAdvanced(table) {
    const rows_body = [...table.querySelector('tbody').children];

    rows_body.forEach(row => {
        const cells = Array.from(row.children);
        let i = 0;
        let del = 50;
        let validate = 0;

        while (i < cells.length) {
            del--;

            if (del < 0) {
                return;
            }

            const cell = cells[i];

            if (cell.classList.contains('nul') && (cell.innerHTML === '&nbsp;' || cell.textContent.trim() === '')) {
                cell.remove()
                let colspan = cell.colSpan || 1;
                let j = i + 1;

                while (j < cells.length) {
                    const nextCell = cells[j];
                    if (nextCell.classList.contains('nul') &&
                        (nextCell.innerHTML === '&nbsp;' || nextCell.textContent.trim() === '')) {
                        colspan += nextCell.colSpan || 1;
                        nextCell.remove();
                    } else {
                        if (row.querySelector('[rowspan]')) {
                            nextCell.innerHTML += `<p class="group">Подгруппа ${i}</p>`;
                            break;
                        }

                        nextCell.innerHTML += `<p class="group">Подгруппа ${i + 1}</p>`;
                        break;
                    }
                    j++;
                }

                if (colspan > 1) {
                    cell.colSpan = colspan;
                }

                i = j;
            } else if (cell.classList.contains('hd0')) {
            } else if (cell.classList.contains('hover')) {
                if (!cell.querySelector('[class^=group]')) {
                    if (row.lastChild === cell) {
                        cell.innerHTML += `<p class="group max">Общая</p>`;
                    } else {
                        cell.innerHTML += `<p class="group">Подгруппа ${i}</p>`;
                    }
                }
                i += cell.colSpan || 1;
                validate++;
            } else {
                i += cell.colSpan || 1;
                validate++;
            }
        }

        if (row.querySelector('[rowspan]') && validate < 3 || validate < 2) {
            const emptyCell = document.createElement('td');
            emptyCell.classList.add('nul');
            emptyCell.innerHTML = '&nbsp;';
            row.appendChild(emptyCell);
        }
    });
}

/**
 * Фикс строки авто подстановки
 * @param text
 * @param add
 * @param pref
 * @returns {string|undefined}
 */
function fix_parse(text, add = '', pref = undefined) {
    return text.search('<!--') === -1 ?  text + add : pref;
}

/**
 * Соединение групп
 * @param table
 */
function groupSimilarPairs(table) {
    const rows = table.querySelectorAll('tr');

    rows.forEach(row => {
        const cells = Array.from(row.querySelectorAll('td.ur'));
        const groups = {};

        cells.forEach(cell => {
            const content = cell.querySelector('.z1')?.textContent.trim() || '';
            if (!groups[content]) groups[content] = [];
            groups[content].push(cell);
        });

        for (const [content, groupCells] of Object.entries(groups)) {
            if (groupCells.length < 1) continue;

            const firstCell = groupCells[0];

            firstCell.innerHTML = `${firstCell.innerHTML}`;

            for (let i = 1; i < groupCells.length; i++) {
                const cell = groupCells[i];
                firstCell.innerHTML += `
                    <div class="subgroup-separator"></div>
                    ${cell.innerHTML}
                `;

                cell.remove();
            }

            firstCell.colSpan = groupCells.length;
        }
    });


    const rows_body_fix = Array.from(table.querySelector('tbody').querySelectorAll('tr'));
    const rows_head_fix = Array.from(table.querySelector('thead').querySelectorAll('td'));

    let max = 0;

    rows_body_fix.forEach(row => {
        if (max < row.childElementCount) {
            max = row.childElementCount;
        }
    });

    let removed = rows_head_fix.splice(3, rows_head_fix.length);

    removed.forEach(e => {
        e.remove()
    })
}

/**
 * Инициализация
 */
document.addEventListener('DOMContentLoaded', () => {
    fix_table();

    const table3 = _id('table-fix');

    if (!table3) {
        return;
    }

    // mergeEmptyCellsAdvanced(table3);
    // groupSimilarPairs(table3);


    /**
     * Все элементы
     * @type {HTMLCollectionOf<HTMLElementTagNameMap[keyof HTMLElementTagNameMap]>}
     */
    const items = _tag("*");


    /**
     * Удаление у всех элементов атрибуты
     */
    for (let i = items.length; i--;) {
        let e = items[i];

        _remove_attr(e, 'style');
        _remove_attr(e, 'height');
        _remove_attr(e, 'width');

        if (e.hasAttribute('onmouseover') || e.hasAttribute('onmouseout')) {
            e.classList.add('hover');
        }

        _remove_attr(e, 'onmouseout');
        _remove_attr(e, 'onmouseover');
    }

});