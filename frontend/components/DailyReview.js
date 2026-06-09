const DailyReview = {
  props: {
    doneItems: Array,
    migItems: Array,
    dropItems: Array,
    interrupt: String,
    nextItems: Array,
    closed: Boolean,
    daySaved: Boolean,
  },
  emits: ['save', 'close', 'update:interrupt'],
  data() {
    return { closing: false, closeAnimating: false };
  },
  methods: {
    async quickClose() {
      this.closing = true;
      this.closeAnimating = true;
      await new Promise(r => setTimeout(r, 400));
      this.$emit('close');
      setTimeout(() => { this.closeAnimating = false; }, 600);
      this.closing = false;
    },
  },
  template: `
    <section class="panel daily-review-panel" :class="{ closing: closeAnimating }">
      <div class="panel-head">
        <div><p class="panel-kicker">日复盘 · 收尾</p><h2>记录成果与阻碍</h2></div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span v-if="closed" class="status-pill" data-tone="ok">已收尾</span>
          <button v-else class="ghost" @click="quickClose" :disabled="closing">{{ closing?'收尾中...':'🚀 一键收尾' }}</button>
          <button class="primary" @click="$emit('save')">保存</button>
        </div>
      </div>

      <div class="two-col" style="margin-bottom:16px;">
        <!-- 完成 + 迁移 合并列 -->
        <div>
          <div style="margin-bottom:12px;">
            <span style="font-size:13px;font-weight:700;color:var(--muted);display:block;margin-bottom:4px;">✅ 完成</span>
            <div v-for="(item,i) in doneItems" :key="'d'+i" class="item-line">
              <input :value="item" @input="doneItems[i]=$event.target.value" @blur="$emit('save')" placeholder="今天做完了什么？" />
              <button class="btn-act btn-act-del" @click="doneItems.splice(i,1);$emit('save')">✕</button>
            </div>
            <button class="btn-add" @click="doneItems.push('');$emit('save')">+ 添加完成项</button>
          </div>
          <div>
            <span style="font-size:13px;font-weight:700;color:var(--muted);display:block;margin-bottom:4px;">➡️ 迁移到明天</span>
            <div v-for="(item,i) in migItems" :key="'m'+i" class="item-line">
              <input :value="item" @input="migItems[i]=$event.target.value" @blur="$emit('save')" placeholder="需要顺延到明天的事" />
              <button class="btn-act btn-act-del" @click="migItems.splice(i,1);$emit('save')">✕</button>
            </div>
            <button class="btn-add" @click="migItems.push('');$emit('save')">+ 添加迁移项</button>
          </div>
        </div>

        <!-- 搁置 + 打断 合并列 -->
        <div>
          <div style="margin-bottom:12px;">
            <span style="font-size:13px;font-weight:700;color:var(--muted);display:block;margin-bottom:4px;">❌ 搁置/放弃</span>
            <div v-for="(item,i) in dropItems" :key="'x'+i" class="item-line">
              <input :value="item" @input="dropItems[i]=$event.target.value" @blur="$emit('save')" placeholder="不再继续的事" />
              <button class="btn-act btn-act-del" @click="dropItems.splice(i,1);$emit('save')">✕</button>
            </div>
            <button class="btn-add" @click="dropItems.push('');$emit('save')">+</button>
          </div>
          <div>
            <span style="font-size:13px;font-weight:700;color:var(--muted);display:block;margin-bottom:4px;">⚠️ 主要打断</span>
            <textarea :value="interrupt" @input="$emit('update:interrupt',$event.target.value)" @blur="$emit('save')" rows="3" placeholder="什么打断了今天的节奏？"></textarea>
          </div>
        </div>
      </div>

      <div>
        <span style="font-size:13px;font-weight:700;color:var(--muted);display:block;margin-bottom:4px;">📌 明日优先</span>
        <div v-for="(item,i) in nextItems" :key="'n'+i" class="item-line">
          <input :value="item" @input="nextItems[i]=$event.target.value" @blur="$emit('save')" @keyup.enter="$event.target.blur()" placeholder="明天第一件事" />
          <button class="btn-act btn-act-del" @click="nextItems.splice(i,1);$emit('save')">✕</button>
        </div>
        <button class="btn-add" @click="nextItems.push('');$emit('save')">+ 添加</button>
      </div>
    </section>
  `,
};
