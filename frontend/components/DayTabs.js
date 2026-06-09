const DayTabs = {
  props: {
    days: Array,
    selectedDay: String,
    dayStatuses: Object,
  },
  emits: ['switch-day'],
  methods: {
    statusClass(date) {
      const s = this.dayStatuses[date];
      if (s === 'closed') return 'day-closed';
      if (s === 'content') return 'day-content';
      return 'day-empty';
    },
    statusLabel(date) {
      const s = this.dayStatuses[date];
      if (s === 'closed') return '已收尾 ✓';
      if (s === 'content') return '有内容';
      return '';
    },
  },
  template: `
    <div class="choice-tabs" style="margin:18px 0 14px;">
      <button v-for="d in days" :key="d.date"
        :class="['choice-chip','mini', statusClass(d.date), {active: selectedDay===d.date}]"
        @click="$emit('switch-day', d.date)"
        :style="d.today ? 'border:2px solid var(--brand);' : ''">
        <span class="choice-chip-label">
          <span v-if="dayStatuses[d.date]==='closed'" style="color:#18a058;margin-right:2px;">●</span>
          <span v-else-if="dayStatuses[d.date]==='content'" style="color:#f0a020;margin-right:2px;">●</span>
          {{ d.label }}<span v-if="d.today" style="font-size:10px;color:var(--brand);"> 今天</span>
        </span>
        <span class="choice-chip-meta">{{ d.date.slice(5) }}</span>
        <span v-if="statusLabel(d.date)" :style="{fontSize:'9px',fontWeight:600,color:dayStatuses[d.date]==='closed'?'#18a058':'#f0a020'}">{{ statusLabel(d.date) }}</span>
      </button>
    </div>
  `,
};
