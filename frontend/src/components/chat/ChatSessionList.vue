<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, Search, Trash2, Pencil, Check, X, MessagesSquare } from 'lucide-vue-next'
import type { ChatSession } from '@/types'

const props = defineProps<{ sessions: ChatSession[]; activeId: string | null }>()
const emit = defineEmits<{
  (e: 'create'): void
  (e: 'select', id: string): void
  (e: 'rename', id: string, title: string): void
  (e: 'remove', id: string): void
}>()

const keyword = ref('')
const editingId = ref<string | null>(null)
const draft = ref('')

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return props.sessions
  return props.sessions.filter((s) => s.title.toLowerCase().includes(q))
})

function startRename(s: ChatSession) {
  editingId.value = s.id
  draft.value = s.title
}

function commitRename() {
  if (editingId.value) emit('rename', editingId.value, draft.value)
  editingId.value = null
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="space-y-2 border-b border-line p-3">
      <button type="button" class="btn-primary w-full" @click="emit('create')">
        <Plus class="size-4" aria-hidden="true" />新建会话
      </button>
      <div class="relative">
        <label class="sr-only" for="session-search">搜索会话</label>
        <Search class="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
        <input id="session-search" v-model="keyword" type="search" class="input pl-8" placeholder="搜索会话…" />
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-2">
      <p v-if="!filtered.length" class="px-2 py-6 text-center text-[12px] text-ink-3">
        {{ sessions.length ? '没有匹配的会话' : '还没有会话，点击上方新建' }}
      </p>
      <ul class="space-y-0.5">
        <li v-for="s in filtered" :key="s.id">
          <div
            :class="[
              'group flex items-start gap-1 rounded-[var(--radius-control)] px-2 py-2',
              s.id === activeId ? 'bg-brand-soft' : 'hover:bg-page',
            ]"
          >
            <button
              type="button"
              class="min-w-0 flex-1 text-left"
              :aria-current="s.id === activeId ? 'true' : undefined"
              @click="emit('select', s.id)"
            >
              <template v-if="editingId === s.id">
                <span class="sr-only">重命名会话</span>
              </template>
              <template v-else>
                <span :class="['block truncate text-[13px]', s.id === activeId ? 'text-brand font-medium' : 'text-ink']">
                  {{ s.title }}
                </span>
                <span class="mt-0.5 flex items-center gap-1 text-[12px] text-ink-3">
                  <MessagesSquare class="size-3" aria-hidden="true" />{{ s.messages.length }} 条 · {{ s.updatedAt }}
                </span>
              </template>
            </button>

            <template v-if="editingId === s.id">
              <input
                v-model="draft"
                class="input h-7 w-full text-[12px]"
                aria-label="会话名称"
                @keydown.enter="commitRename"
                @keydown.esc="editingId = null"
              />
              <button type="button" class="btn-ghost h-7 w-7 p-0" aria-label="保存名称" @click="commitRename">
                <Check class="size-3.5" />
              </button>
              <button type="button" class="btn-ghost h-7 w-7 p-0" aria-label="取消重命名" @click="editingId = null">
                <X class="size-3.5" />
              </button>
            </template>
            <template v-else>
              <button
                type="button"
                class="btn-ghost h-7 w-7 p-0 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                aria-label="重命名会话"
                @click="startRename(s)"
              >
                <Pencil class="size-3.5" />
              </button>
              <button
                type="button"
                class="btn-ghost h-7 w-7 p-0 text-err opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                aria-label="删除会话"
                @click="emit('remove', s.id)"
              >
                <Trash2 class="size-3.5" />
              </button>
            </template>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
