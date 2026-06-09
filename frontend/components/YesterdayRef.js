const YesterdayRef = {
  props: {
    wk: String,
    day: String,
  },
  emits: ['inherit'],
  data() {
    return { refText: '', pendingItems: [], loading: true };
  },
  watch: {
    day: { immediate: true, handler: 'load' },
  },
  methods: {
    async load() {
      this.loading = true;
      const d = new Date(this.day + 'T00:00:00');
      d.setDate(d.getDate() - 1);
      const yd = d.toISOString().split('T')[0];
      try {
        const r = await (await fetch('/api/weeks/' + this.wk + '/days/' + yd)).json();
        if (r.code === 0 && r.data) {
          const f = r.data;
          const parts = [];
          this.pendingItems = [];
          if (f['明日优先']) {
            parts.push('明日:' + f['明日优先'].replace(/\n/g, ' | '));
            this.pendingItems.push(...(f['明日优先'] || '').split('\n').filter(s => s.trim()));
          }
          if (f['收尾_迁移']) {
            parts.push('迁移:' + f['收尾_迁移'].replace(/\n/g, ' | '));
            this.pendingItems.push(...(f['收尾_迁移'] || '').split('\n').filter(s => s.trim()));
          }
          this.refText = parts.join(' ； ') || '无记录';
        } else {
          this.refText = '无记录';
          this.pendingItems = [];
        }
      } catch (e) {
        this.refText = '无记录';
      }
      this.loading = false;
    },
  },
  template: `
    <section v-if="refText!=='无记录'&&!loading" class="panel"
      :style="{padding:'16px 20px',marginBottom:'14px',borderLeft: pendingItems.length?'3px solid #f0a020':'3px solid var(--mint)'}">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:13px;color:var(--muted);flex:1;">💬 昨日参考：{{ refText }}</span>
        <span v-if="pendingItems.length" style="font-size:11px;color:#f0a020;font-weight:600;">{{ pendingItems.length }}条待继承</span>
        <button class="ghost" @click="$emit('inherit', pendingItems)">📥 一键继承到今日</button>
      </div>
    </section>
  `,
};
