<script setup lang="ts">
import { computed, ref } from 'vue'
import { Play, RefreshCw, History, ArrowRight, Info } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { runRetrieval } from '@/services/mockApi'
import type { RetrievalHit } from '@/types'

const workspace = useWorkspaceStore()
const ui = useUiStore()

type Mode = 'bm25' | 'vector' | 'hybrid'

const mode = ref<Mode>('hybrid')
const kbId = ref(workspace.state.knowledgeBases[0]?.id ?? '')
const query = ref('丙酮泄漏怎么处置？')
const topK = ref(workspace.state.settings.retrieval.topK)
const threshold = ref(workspace.state.settings.retrieval.scoreThreshold)
const useRerank = ref(true)
const useMetaFilter = ref(false)

const running = ref(false)
const failed = ref(false)
const result = ref<{ bm25: RetrievalHit[]; vector: RetrievalHit[]; merged: RetrievalHit[] } | null>(null)

const STEPS = [
  { key: 'query', label: '用户查询' },
  { key: 'process', label: '查询处理' },
  { key: 'recall', label: '多路召回' },
  { key: 'rerank', label: '重排序' },
  { key: 'final', label: '最终结果' },
]
const activeStep = ref('query')

// 重排序只改变顺序与分数，不改变候选集合
const reranked = computed<RetrievalHit[]>(() => {
  if (!result.value) return []
  const base = result.value.merged
  if (!useRerank.value) return base
  const scored = base.map((h, i) => ({
    ...h,
    rerankRank: i + 1,
    // 演示用的确定性重排序：应急处置/制度类片段上浮
    rerankScore: Number(((1 - i * 0.12) * (h.section.includes('应急') || h.section.includes('第十二条') ? 1 : 0.8)).toFixed(2)),
  }))
  return [...scored].sort((a, b) => (b.rerankScore ?? 0) - (a.rerankScore ?? 0))
})

const finalHits = computed(() => reranked.value.slice(0, topK.value))

const metrics = computed(() => ({
  recall: 0.87, mrr: 0.79, ndcg: 0.83, latency: 380,
}))

const historyList = ref([
  { id: 'h1', query: '剧毒化学品领用需要几个人在场？', mode: 'hybrid' as Mode, count: 6, at: '2026-10-14 17:30', ms: 372 },
  { id: 'h2', query: '资质过期了该怎么处置？', mode: 'vector' as Mode, count: 4, at: '2026-10-14 16:02', ms: 210 },
  { id: 'h3', query: '丙酮 储存 柜', mode: 'bm25' as Mode, count: 3, at: '2026-10-13 15:44', ms: 96 },
])

function toHits(rows: { docName: string; section: string; text: string; raw: number }[], channel: RetrievalHit['channel']): RetrievalHit[] {
  return rows.map((r, i) => ({
    id: `${channel}-${i}`,
    docName: r.docName,
    section: r.section,
    text: r.text,
    rawScore: r.raw,
    rank: i + 1,
    channel,
  }))
}

async function run() {
  if (!query.value.trim() || running.value) return
  running.value = true
  failed.value = false
  activeStep.value = 'process'
  try {
    const res = await runRetrieval(mode.value)
    result.value = {
      bm25: toHits(res.bm25, 'bm25'),
      vector: toHits(res.vector, 'vector'),
      merged: toHits(res.merged, 'merged'),
    }
    historyList.value.unshift({
      id: `h-${Date.now()}`, query: query.value, mode: mode.value,
      count: res.merged.length, at: '2026-10-15 10:00', ms: 360 + Math.round(Math.random() * 200),
    })
    activeStep.value = 'final'
    ui.toast('检索完成（模拟结果）')
  } catch {
    failed.value = true
    ui.toast('检索失败：模拟故障，请重试', 'error')
  } finally {
    running.value = false
  }
}

function restore(h: typeof historyList.value[number]) {
  query.value = h.query
  mode.value = h.mode
  ui.toast('已恢复该次查询配置，可重新运行', 'info')
}

const modeLabel: Record<Mode, string> = { bm25: '关键词检索 BM25', vector: '向量检索', hybrid: '混合检索' }
</script>

<template>
  <PageHeader title="检索实验室" description="比较不同检索策略的召回过程、排序变化与评估指标。">
    <template #actions>
      <button type="button" class="btn-primary" :disabled="running || !query.trim()" @click="run">
        <Play class="size-4" aria-hidden="true" />{{ running ? '检索中…' : '执行检索' }}
      </button>
    </template>
  </PageHeader>

  <div class="grid grid-cols-1 gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
    <!-- 查询配置 -->
    <section class="panel p-4" aria-labelledby="query-title">
      <h2 id="query-title" class="mb-3 text-[15px] font-semibold text-ink">查询配置</h2>

      <div class="space-y-4">
        <div>
          <label class="label" for="r-kb">知识库</label>
          <select id="r-kb" v-model="kbId" class="input">
            <option v-for="k in workspace.state.knowledgeBases" :key="k.id" :value="k.id">{{ k.name }}</option>
          </select>
        </div>

        <div>
          <label class="label" for="r-query">查询内容</label>
          <textarea id="r-query" v-model="query" rows="3" class="textarea" placeholder="输入要检索的问题或关键词" />
        </div>

        <fieldset>
          <legend class="label">检索模式</legend>
          <div class="space-y-1.5">
            <label v-for="m in (['bm25', 'vector', 'hybrid'] as Mode[])" :key="m" class="flex items-center gap-2 rounded-[var(--radius-control)] border border-line px-3 py-2 text-[13px] has-[:checked]:border-brand has-[:checked]:bg-brand-soft">
              <input v-model="mode" type="radio" :value="m" name="mode" class="accent-[#4F46E5]" />
              {{ modeLabel[m] }}
            </label>
          </div>
        </fieldset>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="label" for="r-topk">Top-K</label>
            <input id="r-topk" v-model.number="topK" type="number" min="1" max="20" class="input tabular-nums" />
          </div>
          <div>
            <label class="label" for="r-threshold">相似度阈值</label>
            <input id="r-threshold" v-model.number="threshold" type="number" min="0" max="1" step="0.05" class="input tabular-nums" />
          </div>
        </div>

        <div class="space-y-2">
          <label class="flex items-center gap-2 text-[13px] text-ink"><input v-model="useRerank" type="checkbox" class="accent-[#4F46E5]" />启用重排序</label>
          <label class="flex items-center gap-2 text-[13px] text-ink"><input v-model="useMetaFilter" type="checkbox" class="accent-[#4F46E5]" />启用元数据过滤（按章节限定）</label>
        </div>

        <button type="button" class="btn-primary w-full" :disabled="running || !query.trim()" @click="run">
          <Play class="size-4" aria-hidden="true" />{{ running ? '检索中…' : '执行检索' }}
        </button>
        <p class="text-[12px] text-ink-3">全部结果为演示数据，不代表真实向量库召回。</p>
      </div>
    </section>

    <div class="space-y-4">
      <!-- 检索流程可视化 -->
      <section class="panel p-4" aria-labelledby="flow-title">
        <h2 id="flow-title" class="mb-3 text-[15px] font-semibold text-ink">检索流程</h2>
        <ol class="flex flex-wrap items-center gap-2">
          <li v-for="(s, i) in STEPS" :key="s.key" class="flex items-center gap-2">
            <button
              type="button"
              :aria-current="activeStep === s.key ? 'step' : undefined"
              :class="[
                'h-8 rounded-[var(--radius-control)] border px-3 text-[12px]',
                activeStep === s.key ? 'border-brand bg-brand-soft font-medium text-brand' : 'border-line text-ink-2 hover:text-ink',
              ]"
              @click="activeStep = s.key"
            >{{ s.label }}</button>
            <ArrowRight v-if="i < STEPS.length - 1" class="size-3.5 text-ink-3" aria-hidden="true" />
          </li>
        </ol>

        <dl class="mt-4 grid grid-cols-2 gap-3 text-[12px] sm:grid-cols-4">
          <div class="rounded-[var(--radius-control)] border border-line p-2.5">
            <dt class="text-ink-3">当前步骤</dt>
            <dd class="mt-0.5 text-ink">{{ STEPS.find((s) => s.key === activeStep)?.label }}</dd>
          </div>
          <div class="rounded-[var(--radius-control)] border border-line p-2.5">
            <dt class="text-ink-3">耗时（模拟）</dt>
            <dd class="mt-0.5 tabular-nums text-ink">{{ result ? '380 ms' : '—' }}</dd>
          </div>
          <div class="rounded-[var(--radius-control)] border border-line p-2.5">
            <dt class="text-ink-3">候选数量</dt>
            <dd class="mt-0.5 tabular-nums text-ink">{{ result?.merged.length ?? '—' }}</dd>
          </div>
          <div class="rounded-[var(--radius-control)] border border-line p-2.5">
            <dt class="text-ink-3">最终结果</dt>
            <dd class="mt-0.5 tabular-nums text-ink">{{ result ? finalHits.length : '—' }}</dd>
          </div>
        </dl>
      </section>

      <section v-if="failed" class="panel border-err/30 bg-err-soft p-4" role="alert">
        <p class="text-[13px] text-err">检索失败：模拟故障，请重试。</p>
        <button type="button" class="btn-danger mt-2" @click="run"><RefreshCw class="size-3.5" aria-hidden="true" />重试</button>
      </section>

      <EmptyState v-else-if="!result" title="尚未执行检索" description="在左侧设置查询内容与检索模式，然后点击“执行检索”。" />

      <template v-else>
        <!-- 多路召回对比 -->
        <section class="panel p-4" aria-labelledby="recall-title">
          <h2 id="recall-title" class="mb-3 text-[15px] font-semibold text-ink">多路召回对比</h2>
          <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div v-if="mode !== 'vector'">
              <h3 class="label">BM25 关键词召回（{{ result.bm25.length }}）</h3>
              <ul class="space-y-2">
                <li v-for="h in result.bm25" :key="h.id" class="rounded-[var(--radius-control)] border border-line p-3">
                  <div class="flex items-center gap-2 text-[12px]">
                    <span class="tabular-nums text-ink-3">#{{ h.rank }}</span>
                    <span class="truncate font-medium text-ink">{{ h.docName }}</span>
                    <span class="text-ink-3">{{ h.section }}</span>
                    <span class="ml-auto tabular-nums text-ink-2">BM25 {{ h.rawScore.toFixed(1) }}</span>
                  </div>
                  <p class="mt-1.5 line-clamp-2 text-[12px] text-ink-2">{{ h.text }}</p>
                </li>
              </ul>
            </div>

            <div v-if="mode !== 'bm25'">
              <h3 class="label">向量召回（{{ result.vector.length }}）</h3>
              <ul class="space-y-2">
                <li v-for="h in result.vector" :key="h.id" class="rounded-[var(--radius-control)] border border-line p-3">
                  <div class="flex items-center gap-2 text-[12px]">
                    <span class="tabular-nums text-ink-3">#{{ h.rank }}</span>
                    <span class="truncate font-medium text-ink">{{ h.docName }}</span>
                    <span class="text-ink-3">{{ h.section }}</span>
                    <span class="ml-auto tabular-nums text-ink-2">余弦 {{ h.rawScore.toFixed(2) }}</span>
                  </div>
                  <p class="mt-1.5 line-clamp-2 text-[12px] text-ink-2">{{ h.text }}</p>
                </li>
              </ul>
            </div>
          </div>

          <p class="mt-3 flex items-start gap-1.5 rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
            <Info class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            BM25 分数与余弦相似度分属不同量纲，不能直接比较大小，只能在同一路内排序。
          </p>
        </section>

        <!-- 重排序结果 -->
        <section class="panel p-4" aria-labelledby="rank-title">
          <div class="mb-3 flex items-center justify-between gap-2">
            <h2 id="rank-title" class="text-[15px] font-semibold text-ink">重排序前后对比</h2>
            <span v-if="useRerank" class="mock-tag">已启用重排序</span>
            <span v-else class="text-[12px] text-ink-3">未启用重排序，展示原始顺序</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[640px] text-[13px]">
              <caption class="sr-only">重排序前后排名与分数变化</caption>
              <thead class="bg-page text-ink-2">
                <tr>
                  <th scope="col" class="h-9 px-3 text-left font-medium">文档 / 小节</th>
                  <th scope="col" class="h-9 px-3 text-left font-medium">片段</th>
                  <th scope="col" class="h-9 px-3 text-right font-medium">原始排名</th>
                  <th scope="col" class="h-9 px-3 text-right font-medium">新排名</th>
                  <th scope="col" class="h-9 px-3 text-right font-medium">重排序分数</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in reranked" :key="h.id" class="border-t border-line">
                  <td class="px-3 py-2.5">
                    <span class="block truncate font-medium text-ink">{{ h.docName }}</span>
                    <span class="text-[12px] text-ink-3">{{ h.section }}</span>
                  </td>
                  <td class="max-w-[280px] px-3 py-2.5"><span class="line-clamp-1 text-ink-2">{{ h.text }}</span></td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-ink-2">#{{ h.rank }}</td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-ink">#{{ h.rerankRank ?? h.rank }}</td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-ink">{{ h.rerankScore?.toFixed(2) ?? '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 最终结果 -->
        <section class="panel p-4" aria-labelledby="final-title">
          <h2 id="final-title" class="mb-3 text-[15px] font-semibold text-ink">最终结果（Top-{{ topK }}）</h2>
          <ul class="space-y-2">
            <li v-for="(h, i) in finalHits" :key="h.id" class="rounded-[var(--radius-control)] border border-line p-3">
              <div class="flex items-center gap-2 text-[12px]">
                <span class="tabular-nums text-ink-3">[{{ i + 1 }}]</span>
                <span class="font-medium text-ink">{{ h.docName }}</span>
                <span class="text-ink-3">{{ h.section }}</span>
                <StatusBadge v-if="useRerank" status="success" label="重排序后" />
              </div>
              <p class="mt-1.5 text-[13px] text-ink-2">{{ h.text }}</p>
            </li>
          </ul>
        </section>
      </template>

      <!-- 评估指标 -->
      <section class="panel p-4" aria-labelledby="metrics-title">
        <h2 id="metrics-title" class="mb-1 text-[15px] font-semibold text-ink">评估指标</h2>
        <p class="mb-3 text-[12px] text-ink-3">预设演示指标，不是真实评估结果。</p>
        <dl class="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div><dt class="text-[12px] text-ink-3">Recall@K</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">{{ metrics.recall.toFixed(2) }}</dd></div>
          <div><dt class="text-[12px] text-ink-3">MRR</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">{{ metrics.mrr.toFixed(2) }}</dd></div>
          <div><dt class="text-[12px] text-ink-3">nDCG@K</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">{{ metrics.ndcg.toFixed(2) }}</dd></div>
          <div><dt class="text-[12px] text-ink-3">检索耗时</dt><dd class="text-[24px] font-semibold tabular-nums text-ink">{{ metrics.latency }}<span class="text-[14px] font-normal text-ink-2"> ms</span></dd></div>
        </dl>
      </section>

      <!-- 检索历史 -->
      <section class="panel" aria-labelledby="history-title">
        <div class="flex items-center gap-2 border-b border-line px-4 py-3">
          <History class="size-4 text-ink-3" aria-hidden="true" />
          <h2 id="history-title" class="text-[15px] font-semibold text-ink">检索历史</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[560px] text-[13px]">
            <caption class="sr-only">最近的检索记录</caption>
            <thead class="bg-page text-ink-2">
              <tr>
                <th scope="col" class="h-9 px-4 text-left font-medium">查询</th>
                <th scope="col" class="h-9 px-4 text-left font-medium">策略</th>
                <th scope="col" class="h-9 px-4 text-right font-medium">结果数</th>
                <th scope="col" class="h-9 px-4 text-right font-medium">耗时</th>
                <th scope="col" class="h-9 px-4 text-left font-medium">时间</th>
                <th scope="col" class="h-9 px-4 text-right font-medium"><span class="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="h in historyList" :key="h.id" class="border-t border-line">
                <td class="max-w-[280px] px-4 py-2.5"><span class="line-clamp-1 text-ink">{{ h.query }}</span></td>
                <td class="px-4 py-2.5 text-ink-2">{{ modeLabel[h.mode] }}</td>
                <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ h.count }}</td>
                <td class="px-4 py-2.5 text-right tabular-nums text-ink-2">{{ h.ms }} ms</td>
                <td class="px-4 py-2.5 tabular-nums text-ink-2">{{ h.at }}</td>
                <td class="px-4 py-2.5 text-right">
                  <button type="button" class="btn-ghost h-7 px-2 text-[12px]" @click="restore(h)">恢复配置</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>
