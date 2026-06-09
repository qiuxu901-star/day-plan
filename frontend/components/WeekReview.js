const WeekReview = {
  props: {
    wk: String,
    reviewText: String,
  },
  emits: ['save', 'generate', 'export'],
  data() {
    return {
      revTab: 'summary',
      dayRecords: [],
      genBusy: false,
      saveBusy: false,
      revSaved: false,
      localText: '',
    };
  },
  watch: {
    reviewText: { immediate: true, handler(v) { this.localText = v || ''; } },
    revTab: { handler(val) { if (val === 'days') this.loadDayRecords(); } },
  },
  methods: {
    async loadDayRecords() {
      try {
        const r = await (await fetch('/api/weeks/' + this.wk + '/days')).json();
        if (r.code === 0 && r.data) {
          this.dayRecords = r.data.map(d => ({
            wd: d['星期'] || '',
            closed: d['收尾状态'] === '已收尾',
            focus: (d['今日重点'] || '').replace(/\n/g, ' · '),
            done: (d['收尾_完成'] || '').replace(/\n/g, ' · '),
            mig: (d['收尾_迁移'] || '').replace(/\n/g, ' · '),
            intr: (d['主要打断'] || ''),
          })).filter(r => r.done || r.mig || r.intr);
        }
      } catch (e) { this.dayRecords = []; }
    },
    async doGenerate() { this.genBusy = true; this.$emit('generate'); this.genBusy = false; },
  },
  template: `
    <section class="panel review-panel">
      <div class="panel-head">
        <div><p class="panel-kicker">周复盘</p><h2>{{ wk }} 回顾</h2></div>
        <div style="display:flex;gap:8px;">
          <button class="ghost" @click="doGenerate" :disabled="genBusy">🪄 自动生成</button>
          <button class="primary" @click="saveBusy=true;$emit('save',localText);revSaved=true;saveBusy=false;setTimeout(()=>revSaved=false,3000)">💾 保存</button>
          <button class="secondary" @click="$emit('export')">📥 导出</button>
        </div>
      </div>

      <p v-if="revSaved" style="color:var(--mint);font-size:12px;">✅ 已保存</p>

      <!-- 日记录：简洁表格 -->
      <div v-if="dayRecords.length" style="margin-bottom:18px;">
        <div style="font-size:12px;font-weight:700;color:var(--muted);margin-bottom:8px;">📋 每日概要</div>
        <div v-for="r in dayRecords" :key="r.wd" style="padding:8px 12px;border-bottom:1px solid var(--line);font-size:13px;display:flex;gap:12px;align-items:flex-start;">
          <span style="font-weight:700;min-width:36px;color:var(--muted);">{{ r.wd }}</span>
          <span v-if="r.closed" style="font-size:11px;color:var(--mint);font-weight:600;">✓</span>
          <span style="flex:1;">
            <span v-if="r.done" style="display:block;">✅ {{ r.done }}</span>
            <span v-if="r.mig" style="display:block;">➡️ {{ r.mig }}</span>
            <span v-if="r.intr" style="display:block;color:var(--muted);">⚠️ {{ r.intr }}</span>
          </span>
        </div>
      </div>

      <label class="field area">
        <span style="font-size:13px;color:var(--muted);">📝 周总结</span>
        <textarea v-model="localText" placeholder="点击「自动生成」汇总本周内容，也可以手动编辑。" style="min-height:200px;"></textarea>
      </label>
    </section>
  `,
};
