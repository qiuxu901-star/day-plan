const DailyFocus = {
  props: {
    focus: Array,
    daySaved: Boolean,
  },
  emits: ['save', 'move', 'reorder', 'add'],
  data() {
    return { saving: false };
  },
  mounted() {
    this._initDrag();
  },
  updated() {
    this._initDrag();
  },
  beforeUnmount() { if (this._cleanup) this._cleanup(); },
  methods: {
    _initDrag() {
      if (this._cleanup) return; // 只初始化一次
      const el = this.$el.querySelector('.focus-list');
      if (!el || !el.children.length) return;
      this._cleanup = useDragSort(el, this.focus, {
        onEnd: () => this.$emit('reorder'),
      });
    },
    moveItem(i, target) {
      const item = this.focus[i];
      if (!item || !item.trim()) return;
      this.focus.splice(i, 1);
      if (!this.focus.length) this.focus.push('');
      this.$emit('move', { item, target });
    },
    addItem() { this.focus.push(''); this.$emit('save'); },
    onInput(i, e) { this.focus[i] = e.target.value; },
  },
  template: `
    <section class="panel daily-panel">
      <div class="panel-head">
        <div><p class="panel-kicker">日计划 · 重点</p><h2>把今天要做的事填清楚</h2></div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span v-if="daySaved" style="color:var(--mint);font-size:12px;font-weight:700;">✓ 已保存</span>
          <button class="primary" @click="$emit('save')" :disabled="saving">{{ saving?'...':'保存' }}</button>
        </div>
      </div>

      <div style="margin-bottom:16px;">
        <span style="font-size:13px;font-weight:700;color:var(--muted);">🎯 今日重点</span>
        <div class="focus-list" style="display:flex;flex-direction:column;gap:4px;">
          <div v-for="(item,i) in focus" :key="i" class="item-line">
            <span class="drag-handle" style="cursor:grab;font-size:16px;user-select:none;padding:0 4px;">⋮⋮</span>
            <input :value="item" @input="onInput(i, $event)" @blur="$emit('save')" @keyup.enter="$event.target.blur()" :placeholder="'重点 '+(i+1)" />
            <button class="btn-act-text" @click="moveItem(i,'done')">完成</button>
            <button class="btn-act-text" @click="moveItem(i,'migrated')">迁移</button>
            <button class="btn-act-text btn-act-del" @click="focus.splice(i,1);$emit('save')">删</button>
          </div>
        </div>
        <button class="btn-add" @click="addItem">+ 添加重点</button>
      </div>
    </section>
  `,
};
