<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CascaderOption } from 'vant'
import type { Location } from '../types'
import { pathText } from '../ui'

const props = defineProps<{
  modelValue: string | null
  locations: Location[]
  label: string
  allowRoot?: boolean // 允许选“顶层”（新建/移动位置时用）
  excludeId?: string // 排除某个位置及其所有下级（移动位置时防止形成循环）
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()

const show = ref(false)
const HERE = 'here:'
const ROOT = 'root'

const options = computed<CascaderOption[]>(() => {
  const visible = props.locations.filter(
    (l) => !props.excludeId || !l.path.some((p) => p.id === props.excludeId),
  )
  const byParent = new Map<string | null, Location[]>()
  for (const l of visible) {
    const siblings = byParent.get(l.parent_id) ?? []
    siblings.push(l)
    byParent.set(l.parent_id, siblings)
  }
  const build = (parentId: string | null): CascaderOption[] =>
    (byParent.get(parentId) ?? []).map((l) => {
      const children = build(l.id)
      return children.length
        ? { text: l.name, value: l.id, children: [{ text: `就放在「${l.name}」`, value: HERE + l.id }, ...children] }
        : { text: l.name, value: l.id }
    })
  const tree = build(null)
  return props.allowRoot ? [{ text: '顶层（不放在任何位置里）', value: ROOT }, ...tree] : tree
})

const display = computed(() => {
  if (props.modelValue === null) return props.allowRoot ? '顶层' : ''
  const loc = props.locations.find((l) => l.id === props.modelValue)
  return loc ? pathText(loc.path) : ''
})

function onFinish({ selectedOptions }: { selectedOptions: CascaderOption[] }) {
  const value = String(selectedOptions[selectedOptions.length - 1].value)
  emit('update:modelValue', value === ROOT ? null : value.startsWith(HERE) ? value.slice(HERE.length) : value)
  show.value = false
}
</script>

<template>
  <van-field :model-value="display" :label="label" placeholder="请选择" readonly is-link @click="show = true" />
  <van-popup v-model:show="show" round position="bottom">
    <van-cascader :title="`选择${label}`" :options="options" @close="show = false" @finish="onFinish" />
  </van-popup>
</template>
