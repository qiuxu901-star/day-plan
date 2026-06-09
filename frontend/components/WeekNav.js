const WeekNav = {
  props: {
    wk: String,
    weekOpts: Array,
  },
  emits: ['switch-week', 'create-week'],
  template: `
    <section class="panel" style="padding:14px 20px;">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <button class="secondary" @click="$emit('switch-week', -1)" style="padding:8px 14px;">◀</button>
        <button v-for="w in weekOpts" :key="w.key"
          :class="['choice-chip','compact',{active:wk===w.key}]"
          @click="$emit('switch-week', w.key)">{{ w.key }}</button>
        <button class="secondary" @click="$emit('switch-week', 1)" style="padding:8px 14px;">▶</button>
        <span style="flex:1;"></span>
        <button class="secondary" @click="$emit('create-week')" style="font-size:12px;">+新增周</button>
      </div>
    </section>
  `,
};
