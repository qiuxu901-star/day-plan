const TaskPool = {
  props: {
    tasks: Array,
  },
  emits: ['toggle', 'delete', 'add', 'reorder', 'add-to-focus'],
  data() {
    return { showForm: false, newContent: '', newType: '必须完成' };
  },
  computed: {
    progress() {
      const total = this.tasks.length;
      const done = this.tasks.filter(t => t['完成状态']).length;
      return { total, done, rate: total ? Math.round(done / total * 100) : 0 };
    },
  },
  watch: {
    tasks: {
      handler() { this.$nextTick(() => this._initDrag()); },
    },
  },
  mounted() {
    this.$nextTick(() => this._initDrag());
  },
  beforeUnmount() { if (this._cleanup) this._cleanup(); },
  methods: {
    _initDrag() {
      if (this._cleanup) return; // 只初始化一次
      const el = this.$el.querySelector('.task-list');
      if (!el || !el.children.length) return;
      this._cleanup = useDragSort(el, this.tasks, {
        onEnd: () => this.$emit('reorder', this.tasks.map(t => t.record_id)),
      });
    },
    submit() {
      if (!this.newContent.trim()) return;
      this.$emit('add', { content: this.newContent.trim(), task_type: this.newType });
      this.newContent = '';
      this.showForm = false;
    },
    typeClass(type) {
      if (type === '必须完成') return 'type-must';
      if (type === '推进即可') return 'type-push';
      return 'type-temp';
    },
  },
  template: `
    <section class="panel" style="padding:16px 20px;margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-size:13px;font-weight:700;color:var(--muted);">📦 周任务池 · 点击任务文字即可加入今日重点</span>
        <button class="primary" @click="showForm=!showForm" style="font-size:12px;padding:6px 12px;">{{ showForm?'取消':'+ 添加' }}</button>
      </div>

      <div v-if="tasks.length" style="display:flex;align-items:center;gap:10px;margin-bottom:10px;padding:6px 12px;background:rgba(18,125,124,0.05);border-radius:10px;">
        <span style="font-size:12px;font-weight:700;color:var(--mint);white-space:nowrap;">📊 {{ progress.done }}/{{ progress.total }}</span>
        <div style="flex:1;height:5px;background:#e0ddd6;border-radius:3px;"><div :style="{width:progress.rate+'%',height:'100%',background:'var(--mint)',borderRadius:'3px',transition:'width .3s'}"></div></div>
        <span style="font-size:11px;color:var(--muted);white-space:nowrap;">{{ progress.rate }}%</span>
      </div>

      <div class="task-list" v-if="tasks.length" style="display:flex;flex-direction:column;gap:4px;">
        <div v-for="t in tasks" :key="t.record_id"
          style="display:flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,0.6);">
          <span class="drag-handle" style="cursor:grab;font-size:16px;user-select:none;padding:0 4px;">⋮⋮</span>
          <input type="checkbox" :checked="t['完成状态']" @change="$emit('toggle', t)" style="width:18px;height:18px;min-height:0;flex-shrink:0;" />
          <span :style="{fontSize:'13px',textDecoration:t['完成状态']?'line-through':'none',opacity:t['完成状态']?0.4:1,cursor:'pointer',flex:1}" @click="$emit('add-to-focus', t['任务内容'])">{{ t['任务内容'] }}</span>
          <span :style="{fontSize:'10px',padding:'2px 7px',borderRadius:'99px',fontWeight:600}" :class="typeClass(t['任务类型'])">{{ t['任务类型'] }}</span>
          <button style="color:var(--muted);background:none;border:none;cursor:pointer;font-size:13px;flex-shrink:0;" @click="$emit('delete', t.record_id)">✕</button>
        </div>
      </div>

      <div v-if="showForm" class="toolbar" style="margin-top:8px;">
        <input v-model="newContent" placeholder="任务..." style="flex:1;min-height:42px;" @keyup.enter="submit" />
        <select v-model="newType" style="width:auto;min-height:42px;"><option>必须完成</option><option>推进即可</option><option>临时进入</option></select>
        <button class="primary" @click="submit" style="font-size:13px;">添加</button>
      </div>

      <p v-if="!tasks.length&&!showForm" style="text-align:center;font-size:12px;color:var(--muted);padding:10px;">暂无任务。在「周计划」中定义任务后，这里会出现本周任务池</p>
    </section>
  `,
};
