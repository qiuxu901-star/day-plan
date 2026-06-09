const WeekReview = {
  props: {
    wk: String,
    reviewText: String,
  },
  emits: ['save', 'generate', 'export'],
  data() {
    return {
      revTab: 'days',
      dayRecords: [],
      genBusy: false,
      saveBusy: false,
      revSaved: false,
      localText: '',
    };
  },
  watch: {
    reviewText: { immediate: true, handler(v) { this.localText = v || ''; } },
    revTab: { immediate: true, handler(val) { if (val === 'days') this.loadDayRecords(); } },
  },
  methods: {
    async loadDayRecords() {
      try {
        const r = await (await fetch('/api/weeks/' + this.wk + '/days')).json();
        if (r.code === 0 && r.data) {
          this.dayRecords = r.data.map(d => ({
            wd: d['星期'] || '',
            closed: d['收尾状态'] === '已收尾',
            done: (d['收尾_完成'] || '').replace(/\n/g, ' | '),
            mig: (d['收尾_迁移'] || '').replace(/\n/g, ' | '),
            intr: (d['主要打断'] || '').replace(/\n/g, ' | '),
          }));
        }
      } catch (e) { this.dayRecords = []; }
    },
  },
  template: `
    <section class="panel review-panel">
      <div class="panel-head"><div><p class="panel-kicker">周复盘</p><h2>{{ wk }} 回顾</h2></div></div>
      <div class="choice-tabs" style="margin-bottom:14px;">
        <button :class="['choice-chip','mini',{active:revTab==='days'}]" @click="revTab='days'">📋 日记录</button>
        <button :class="['choice-chip','mini',{active:revTab==='summary'}]" @click="revTab='summary'">📊 周总结</button>
      </div>

      <div v-if="revTab==='days'">
        <div v-if="dayRecords.length" style="display:flex;flex-direction:column;gap:14px;">
          <div v-for="r in dayRecords" :key="r.wd" style="padding:14px;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,0.5);">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;"><strong>{{ r.wd }}</strong><span v-if="r.closed" class="status-pill" data-tone="ok" style="font-size:11px;">已收尾</span></div>
            <div v-if="r.done" style="font-size:14px;margin-bottom:2px;">✅ {{ r.done }}</div>
            <div v-if="r.mig" style="font-size:14px;margin-bottom:2px;">➡️ {{ r.mig }}</div>
            <div v-if="r.intr" style="font-size:14px;">⚠️ {{ r.intr }}</div>
            <div v-if="!r.done&&!r.mig&&!r.intr" style="font-size:13px;color:var(--muted);">暂无记录</div>
          </div>
        </div>
        <p v-else style="text-align:center;padding:20px;color:var(--muted);">暂无日记录</p>
      </div>

      <div v-if="revTab==='summary'">
        <div style="display:flex;gap:8px;margin-bottom:14px;">
          <button class="ghost" @click="$emit('generate')" :disabled="genBusy">🪄 自动生成</button>
          <button class="primary" @click="saveBusy=true;$emit('save',localText);revSaved=true;saveBusy=false;setTimeout(()=>revSaved=false,3000)">💾 保存</button>
          <button class="secondary" @click="$emit('export')">📥 导出</button>
        </div>
        <p v-if="revSaved" style="color:var(--mint);">✅ 已保存</p>
        <label class="field area"><textarea v-model="localText" placeholder="点击「自动生成」汇总。"></textarea></label>
      </div>
    </section>
  `,
};
