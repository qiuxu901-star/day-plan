/**
 * SortableJS 封装 composable。
 * 用法：useDragSort(containerEl, items, { onEnd: (items) => save(items) })
 * 返回 cleanup 函数。
 */
function useDragSort(el, items, opts = {}) {
  if (!el || typeof Sortable === 'undefined') return () => {};

  const instance = Sortable.create(el, {
    animation: 150,
    handle: '.drag-handle',
    ghostClass: 'sortable-ghost',
    dragClass: 'sortable-drag',
    onEnd(evt) {
      const moved = items.splice(evt.oldIndex, 1)[0];
      items.splice(evt.newIndex, 0, moved);
      if (opts.onEnd) opts.onEnd(items);
    },
    ...opts,
  });

  return () => instance.destroy();
}
