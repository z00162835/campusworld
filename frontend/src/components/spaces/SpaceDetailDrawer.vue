<script setup lang="ts">
/**
 * SpaceDetailDrawer - Detail view/edit drawer for space nodes
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSpacesStore } from '@/stores/spaces'
import { ElMessage } from 'element-plus'
import {
  WORLD_TYPE_OPTIONS,
  BUILDING_TYPE_OPTIONS,
  FLOOR_TYPE_OPTIONS,
  ROOM_TYPE_OPTIONS,
  BUILDING_STATUS_OPTIONS,
  WORLD_STATUS_OPTIONS,
  getSelectOptionLabel,
} from '@/types/space'
import { spacesApi } from '@/api/spaces'
import type { SelectOption, SpaceNode } from '@/types/space'

const props = defineProps<{
  visible: boolean
  node: SpaceNode | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  refresh: []
}>()

const store = useSpacesStore()
const { t } = useI18n()
const isEditing = ref(false)
const isSaving = ref(false)
const editForm = ref<any>({})

const drawerVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

watch(() => props.node, (node) => {
  if (node) {
    editForm.value = { ...node, ...node.attributes }
  }
  isEditing.value = false
})

const handleClose = () => {
  drawerVisible.value = false
  isEditing.value = false
}

const handleEdit = () => {
  isEditing.value = true
}

const handleCancel = () => {
  if (props.node) {
    editForm.value = { ...props.node, ...props.node.attributes }
  }
  isEditing.value = false
}

const handleSave = async () => {
  if (!props.node) return

  isSaving.value = true
  try {
    const updateData: any = {
      name: editForm.value.name,
      description: editForm.value.description,
    }

    // Add type-specific fields
    if (store.activeTab === 'world') {
      updateData.world_type = editForm.value.world_type
      updateData.status = editForm.value.status
    } else if (store.activeTab === 'building') {
      updateData.building_type = editForm.value.building_type
      updateData.world_id = editForm.value.world_id
      updateData.status = editForm.value.status
    } else if (store.activeTab === 'floor') {
      updateData.floor_type = editForm.value.floor_type
      updateData.building_id = editForm.value.building_id
    } else if (store.activeTab === 'room') {
      updateData.room_type = editForm.value.room_type
      updateData.floor_id = editForm.value.floor_id
    }

    await spacesApi.updateSpace(props.node.id, updateData)
    ElMessage.success(t('spaces.drawer.updateSuccess'))
    isEditing.value = false
    emit('refresh')
  } catch (error) {
    ElMessage.error(t('spaces.drawer.updateFailed'))
  } finally {
    isSaving.value = false
  }
}

const getFieldOptionLabel = (field: DetailField) => {
  const value = editForm.value[field.prop]
  const option = field.options?.find(o => o.value === value)
  return option ? getSelectOptionLabel(option, t) : value
}

interface DetailField {
  label: string
  prop: string
  type?: 'select' | 'text' | 'date'
  options?: SelectOption[]
}

const detailFields = computed<DetailField[]>(() => {
  if (!props.node) return []

  const base: DetailField[] = [
    { label: t('spaces.fields.name'), prop: 'name' },
    { label: t('spaces.fields.description'), prop: 'description' },
  ]

  switch (store.activeTab) {
    case 'world':
      return [
        ...base,
        { label: t('spaces.fields.worldType'), prop: 'world_type', type: 'select', options: WORLD_TYPE_OPTIONS },
        { label: t('spaces.fields.status'), prop: 'status', type: 'select', options: WORLD_STATUS_OPTIONS },
        { label: t('spaces.fields.createdAt'), prop: 'created_at', type: 'date' },
      ]
    case 'building':
      return [
        ...base,
        { label: t('spaces.fields.buildingType'), prop: 'building_type', type: 'select', options: BUILDING_TYPE_OPTIONS },
        { label: t('spaces.fields.world'), prop: 'world_id', type: 'text' },
        { label: t('spaces.fields.status'), prop: 'status', type: 'select', options: BUILDING_STATUS_OPTIONS },
      ]
    case 'floor':
      return [
        ...base,
        { label: t('spaces.fields.floorType'), prop: 'floor_type', type: 'select', options: FLOOR_TYPE_OPTIONS },
        { label: t('spaces.fields.building'), prop: 'building_id', type: 'text' },
      ]
    case 'room':
      return [
        ...base,
        { label: t('spaces.fields.roomType'), prop: 'room_type', type: 'select', options: ROOM_TYPE_OPTIONS },
        { label: t('spaces.fields.floor'), prop: 'floor_id', type: 'text' },
      ]
    default:
      return base
  }
})
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="isEditing ? t('spaces.drawer.editTitle') : t('spaces.drawer.detailTitle')"
    size="480px"
    @close="handleClose"
  >
    <div v-if="props.node" class="drawer-content">
      <!-- View Mode -->
      <template v-if="!isEditing">
        <el-descriptions :column="1" border>
          <el-descriptions-item
            v-for="field in detailFields"
            :key="field.prop"
            :label="field.label"
          >
            <template v-if="field.type === 'select'">
              <el-tag v-if="field.options">
                {{ getFieldOptionLabel(field) }}
              </el-tag>
              <span v-else>{{ editForm[field.prop] }}</span>
            </template>
            <span v-else>{{ editForm[field.prop] || '-' }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="action-buttons">
          <el-button type="primary" @click="handleEdit">
            {{ $t('common.edit') }}
          </el-button>
        </div>
      </template>

      <!-- Edit Mode -->
      <template v-else>
        <el-form :model="editForm" label-width="100px">
          <el-form-item :label="t('spaces.fields.name')">
            <el-input v-model="editForm.name" />
          </el-form-item>

          <el-form-item :label="t('spaces.fields.description')">
            <el-input v-model="editForm.description" type="textarea" :rows="3" />
          </el-form-item>

          <el-form-item
            v-for="field in detailFields.filter(f => f.type === 'select')"
            :key="field.prop"
            :label="field.label"
          >
            <el-select v-model="editForm[field.prop]" :placeholder="t('spaces.filters.select')" style="width: 100%">
              <el-option
                v-for="opt in field.options"
                :key="opt.value"
                :label="getSelectOptionLabel(opt, t)"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-form>

        <div class="action-buttons">
          <el-button @click="handleCancel">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="isSaving" @click="handleSave">
            {{ t('common.save') }}
          </el-button>
        </div>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.drawer-content {
  padding: 0 16px;
}

.drawer-content :deep(.el-descriptions) {
  color: var(--text-primary);
}

.drawer-content :deep(.el-descriptions__label) {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border-color: var(--border-color);
}

.drawer-content :deep(.el-descriptions__content) {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-color: var(--border-color);
}

.drawer-content :deep(.el-tag) {
  background: var(--bg-hover);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-md);
  margin-top: var(--spacing-xl);
}

.action-buttons :deep(.el-button) {
  background: var(--bg-secondary);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

.action-buttons :deep(.el-button:hover) {
  background: var(--bg-hover);
  border-color: var(--border-color-dark);
  color: var(--text-primary);
}

.action-buttons :deep(.el-button--primary) {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
}

.action-buttons :deep(.el-button--primary:hover) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}
</style>
