const WeekPlan = {
  props: {
    weekData: Object,
  },
  emits: ['save', 'promote-temp'],
  data() {
    return {
      fields: {
        mainLine: [],
        mustComplete: [],
        pushForward: [],
        tempIn: [],
      },
      saving: false,
      saved: false,
    };
  },
  watch: {
    weekData: {
      immediate: true,
      deep: true,
      handler(val) {
        if (val && Object.keys(val).length) {
          this.fields.mainLine = (val['本周主线'] || '').split('\n').filter(l => l.trim());
          this.fields.mustComplete = (val['本周必须完成'] || '').split('\n').filter(l => l.trim());
          this.fields.pushForward = (val['本周推进即可'] || '').split('\n').filter(l => l.trim());
          this.fields.tempIn = (val['临时进入'] || '').split('\n').filter(l => l.trim());
        }
        this.ensureOne();
      },
    },
  },
  methods: {
    ensureOne() {
      ['mainLine', 'mustComplete', 'pushForward', 'tempIn'].forEach(k => {
        if (!this.fields[k].length) this.fields[k] = [''];
      });
    },
    addItem(field) { this.fields[field].push(''); },
    removeItem(field, i) { this.fields[field].splice(i, 1); this.ensureOne(); this.debouncedSave(); },
    onInput(field, i, e) { this.fields[field][i] = e.target.value; },
    debouncedSave() {
      clearTimeout(this._st);
      this._st = setTimeout(() => this.doSave(), 500);
    },
    async doSave() {
      this.saving = true;
      const payload = {
        '本周主线': this.fields.mainLine.filter(s => s.trim()).join('\n'),
        '本周必须完成': this.fields.mustComplete.filter(s => s.trim()).join('\n'),
        '本周推进即可': this.fields.pushForward.filter(s => s.trim()).join('\n'),
        '临时进入': this.fields.tempIn.filter(s => s.trim()).join('\n'),
      };
      this.$emit('save', payload);
      this.saved = true;
      this.saving = false;
      setTimeout(() => this.saved = false, 2000);
    },
    promoteTempToTasks() {
      this.$emit('promote-temp', this.fields.tempIn.filter(s => s.trim()));
    },
  },
  template: `
    <section class="panel weekly-panel">
      <div class="panel-head">
        <div><p class="panel-kicker">周计划 · 方向</p><h2>先把本周方向定住</h2></div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span v-if="saved" style="color:var(--mint);font-size:12px;font-weight:700;">✓ 已保存</span>
          <button class="primary" @click="doSave" :disabled="saving">{{ saving?'...':'保存' }}</button>
        </div>
      </div>

      <div class="two-col">
        <div v-for="(cfg, key) in [
          {key:'mainLine',label:'本周主线',placeholder:'每条一行。不是任务清单，是方向。'},
          {key:'mustComplete',label:'本周必须完成',placeholder:'每条一行。'},
          {key:'pushForward',label:'本周推进即可',placeholder:'每条一行。'},
          {key:'tempIn',label:'临时进入',placeholder:'新任务缓冲区。'}
        ]" :key="cfg.key" style="display:flex;flex-direction:column;gap:6px;">
          <span style="font-size:13px;font-weight:600;color:var(--muted);">{{ cfg.label }}</span>
          <div v-for="(item, i) in fields[cfg.key]" :key="cfg.key+i" style="display:flex;align-items:center;gap:6px;">
            <span class="drag-handle" style="color:#ccc;cursor:grab;font-size:14px;user-select:none;">⠿</span>
            <input :value="item" @input="onInput(cfg.key, i, $event)" @blur="debouncedSave"
              :placeholder="cfg.placeholder"
              style="flex:1;min-height:42px;padding:8px 12px;border-radius:12px;border:1px solid rgba(41,31,18,.12);background:rgba(255,255,255,.82);font-size:14px;" />
            <button @click="removeItem(cfg.key, i)" style="width:28px;height:28px;border-radius:50%;border:1.5px solid var(--line);background:rgba(255,255,255,.7);color:var(--muted);cursor:pointer;flex-shrink:0;font-size:13px;">✕</button>
          </div>
          <button @click="addItem(cfg.key)" style="width:100%;padding:10px;border:1.5px dashed var(--line);border-radius:14px;background:transparent;color:var(--muted);font-size:13px;cursor:pointer;">+ 添加</button>
        </div>
      </div>

      <div v-if="fields.tempIn.some(s=>s.trim())" style="margin-top:12px;">
        <button class="ghost" @click="promoteTempToTasks" style="font-size:12px;">📦 将「临时进入」批量创建为周任务</button>
      </div>
    </section>
  `,
};
