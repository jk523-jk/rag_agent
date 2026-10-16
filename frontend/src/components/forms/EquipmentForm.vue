<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { Equipment } from '@/types'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import { newId } from '@/utils/format'
import {
  EQUIP_CATEGORY_OPTIONS, EQUIP_STATUS_OPTIONS, validateEquipment, type EquipmentDraft,
} from '@/utils/validators'
import AppDrawer from '@/components/common/AppDrawer.vue'

const props = defineProps<{ open: boolean; equipment: Equipment | null }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void; (e: 'saved', equipment: Equipment): void }>()

const workspace = useWorkspaceStore()
const ui = useUiStore()

function blank(): EquipmentDraft {
  return {
    equipId: '', equipName: '', category: '分析仪器', modelNo: '',
    labId: workspace.state.labs[0]?.labId ?? '', keeperId: null,
    status: '在用', calibrateDue: '', purchaseDate: '', remark: '',
  }
}

const form = reactive<EquipmentDraft>(blank())
const errors = ref<Partial<Record<keyof EquipmentDraft, string>>>({})
const submitting = ref(false)

watch(() => props.open, (v) => {
  if (!v) return
  errors.value = {}
  const e = props.equipment
  Object.assign(form, e
    ? {
        equipId: e.equipId, equipName: e.equipName, category: e.category, modelNo: e.modelNo,
        labId: e.labId, keeperId: e.keeperId, status: e.status,
        calibrateDue: e.calibrateDue ?? '', purchaseDate: e.purchaseDate, remark: e.remark,
      }
    : blank())
})

const title = computed(() => (props.equipment ? '编辑设备' : '新增设备'))

/** 储存设施无校准要求，选择该类别时给出提示 */
const isStorage = computed(() => form.category === '储存设施')

function submit() {
  const existing = workspace.state.equipment
    .filter((e) => e.id !== props.equipment?.id)
    .map((e) => e.equipId)
  errors.value = validateEquipment(form, existing, props.equipment?.equipId)
  if (Object.keys(errors.value).length) {
    ui.toast('请修正表单中标红的字段', 'error')
    return
  }
  submitting.value = true
  const entity: Equipment = {
    id: props.equipment?.id ?? newId('eq'),
    equipId: form.equipId.trim(),
    equipName: form.equipName.trim(),
    category: form.category,
    modelNo: form.modelNo.trim(),
    labId: form.labId,
    keeperId: form.keeperId,
    status: form.status,
    // 储存设施无校准要求，一律置空，避免留下误导性的日期
    calibrateDue: isStorage.value ? null : (form.calibrateDue || null),
    purchaseDate: form.purchaseDate,
    remark: form.remark.trim(),
  }
  const i = workspace.state.equipment.findIndex((e) => e.id === entity.id)
  if (i >= 0) workspace.state.equipment[i] = entity
  else workspace.state.equipment.push(entity)
  submitting.value = false
  emit('saved', entity)
  emit('update:open', false)
  ui.toast(props.equipment ? '设备已更新' : '设备已新增')
}
</script>

<template>
  <AppDrawer :open="open" :title="title" width="lg" @update:open="emit('update:open', $event)">
    <form id="equipment-form" class="space-y-4" novalidate @submit.prevent="submit">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="label" for="eq-id">设备编号 <span class="text-err">*</span></label>
          <input id="eq-id" v-model="form.equipId" class="input font-mono" placeholder="EQ-0009" maxlength="32" :aria-invalid="!!errors.equipId" aria-describedby="eq-id-err" />
          <p v-if="errors.equipId" id="eq-id-err" class="mt-1 text-[12px] text-err">{{ errors.equipId }}</p>
        </div>
        <div>
          <label class="label" for="eq-name">设备名称 <span class="text-err">*</span></label>
          <input id="eq-name" v-model="form.equipName" class="input" maxlength="64" :aria-invalid="!!errors.equipName" aria-describedby="eq-name-err" />
          <p v-if="errors.equipName" id="eq-name-err" class="mt-1 text-[12px] text-err">{{ errors.equipName }}</p>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="label" for="eq-cat">设备类别</label>
          <select id="eq-cat" v-model="form.category" class="input">
            <option v-for="c in EQUIP_CATEGORY_OPTIONS" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div>
          <label class="label" for="eq-model">规格型号</label>
          <input id="eq-model" v-model="form.modelNo" class="input" maxlength="64" :aria-invalid="!!errors.modelNo" />
          <p v-if="errors.modelNo" class="mt-1 text-[12px] text-err">{{ errors.modelNo }}</p>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="label" for="eq-lab">所在实验室 <span class="text-err">*</span></label>
          <select id="eq-lab" v-model="form.labId" class="input" :aria-invalid="!!errors.labId">
            <option v-for="l in workspace.state.labs" :key="l.labId" :value="l.labId">{{ l.labId }} {{ l.labName }}</option>
          </select>
          <p v-if="errors.labId" class="mt-1 text-[12px] text-err">{{ errors.labId }}</p>
        </div>
        <div>
          <label class="label" for="eq-keeper">保管人</label>
          <select id="eq-keeper" v-model="form.keeperId" class="input">
            <option :value="null">未指定</option>
            <option v-for="p in workspace.state.persons" :key="p.id" :value="p.id">{{ p.name }}（{{ p.empNo }}）</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="label" for="eq-status">设备状态</label>
          <select id="eq-status" v-model="form.status" class="input">
            <option v-for="s in EQUIP_STATUS_OPTIONS" :key="s" :value="s">{{ s }}</option>
          </select>
          <p class="mt-1 text-[12px] text-ink-3">仅「在用」的设备可借出。</p>
        </div>
        <div>
          <label class="label" for="eq-cal">校准有效期至</label>
          <input
            id="eq-cal"
            v-model="form.calibrateDue"
            type="date"
            class="input tabular-nums"
            :disabled="isStorage"
            :aria-invalid="!!errors.calibrateDue"
          />
          <p v-if="errors.calibrateDue" class="mt-1 text-[12px] text-err">{{ errors.calibrateDue }}</p>
          <p v-else-if="isStorage" class="mt-1 text-[12px] text-ink-3">储存设施无校准要求，无需填写。</p>
        </div>
      </div>

      <div>
        <label class="label" for="eq-purchase">购置日期</label>
        <input id="eq-purchase" v-model="form.purchaseDate" type="date" class="input tabular-nums" :aria-invalid="!!errors.purchaseDate" />
        <p v-if="errors.purchaseDate" class="mt-1 text-[12px] text-err">{{ errors.purchaseDate }}</p>
      </div>

      <div>
        <label class="label" for="eq-remark">备注</label>
        <textarea id="eq-remark" v-model="form.remark" class="textarea" rows="2" maxlength="200" :aria-invalid="!!errors.remark" />
        <p v-if="errors.remark" class="mt-1 text-[12px] text-err">{{ errors.remark }}</p>
      </div>

      <p class="rounded-[var(--radius-control)] bg-info-soft px-3 py-2 text-[12px] text-info">
        本系统只读：这里的改动仅保存在浏览器演示数据中，不会写入真实资产台账。真实环境需走设备管理部门审批。
      </p>
    </form>

    <template #footer>
      <button type="button" class="btn-default" @click="emit('update:open', false)">取消</button>
      <button type="submit" form="equipment-form" class="btn-primary" :disabled="submitting">
        {{ submitting ? '保存中…' : '保存' }}
      </button>
    </template>
  </AppDrawer>
</template>
