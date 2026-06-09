/**
 * 全局键盘快捷键 composable。
 * 用法：useKeyboard({ 'Ctrl+S': () => save(), 'ArrowLeft': () => prev() })
 * 输入框聚焦时不拦截单键（仅组合键生效）。
 * 返回 cleanup 函数。
 */
function useKeyboard(shortcuts) {
  function handler(e) {
    const tag = e.target.tagName;
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable;

    // 单键（无修饰符）在输入框内不拦截
    const hasMod = e.ctrlKey || e.metaKey || e.altKey;
    if (isInput && !hasMod) return;

    const key = [];
    if (e.ctrlKey || e.metaKey) key.push('Ctrl');
    if (e.altKey) key.push('Alt');
    if (e.shiftKey) key.push('Shift');
    key.push(e.key.length === 1 ? e.key.toUpperCase() : e.key);

    const combo = key.join('+');
    const action = shortcuts[combo] || shortcuts[e.key];
    if (action) {
      e.preventDefault();
      action();
    }
  }

  document.addEventListener('keydown', handler);
  return () => document.removeEventListener('keydown', handler);
}
