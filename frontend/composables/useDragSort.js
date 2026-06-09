/**
 * SortableJS 封装 composable（Vue 3 兼容版）。
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
    forceFallback: true,       // 避免原生 drag 与 Vue DOM 冲突
    fallbackTolerance: 3,
    onEnd(evt) {
      // 仅更新数据数组，由 Vue 负责 DOM 重排
      const moved = items.splice(evt.oldIndex, 1)[0];
      items.splice(evt.newIndex, 0, moved);
      if (opts.onEnd) opts.onEnd(items);
    },
  });

  return () => instance.destroy();
}
