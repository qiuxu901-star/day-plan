/**
 * SortableJS 封装 composable（Vue 3 兼容版）。
 * 用法：useDragSort(containerEl, items, { onEnd: (items) => save(items) })
 * 返回 cleanup 函数。调用前确保 container 和 items 已存在。
 */
function useDragSort(el, items, opts = {}) {
  if (!el || typeof Sortable === 'undefined') return () => {};
  // ensure items exist before binding
  if (!el.children || !el.children.length) return () => {};

  const instance = Sortable.create(el, {
    animation: 150,
    handle: '.drag-handle',
    ghostClass: 'sortable-ghost',
    dragClass: 'sortable-drag',
    onEnd(evt) {
      // 拖拽结束：更新数据数组，Vue 负责重排 DOM
      if (evt.oldIndex === evt.newIndex) return;
      const moved = items.splice(evt.oldIndex, 1)[0];
      items.splice(evt.newIndex, 0, moved);
      if (opts.onEnd) opts.onEnd(items);
    },
  });

  return () => instance.destroy();
}
