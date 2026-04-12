<script setup lang="ts">
/**
 * SpaceDetailDrawer - Detail view/edit drawer for space nodes
 */
import { ref, computed, watch } from 'vue'
import { useSpacesStore } from '@/stores/spaces'
import { ElMessage } from 'element-plus'
import {
  WORLD_TYPE_OPTIONS,
  BUILDING_TYPE_OPTIONS,
  FLOOR_TYPE_OPTIONS,
  ROOM_TYPE_OPTIONS,
  BUILDING_STATUS_OPTIONS,
  WORLD_STATUS_OPTIONS,
} from '@/types/space'
import { spacesApi } from '@/api/spaces'
import type { SpaceNode } from '@/types/space'

const props = defineProps<{
  visible: boolean
  node: SpaceNode | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  refresh: []
}>()

const store = useSpacesStore()
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
    ElMessage.success('更新成功')
    isEditing.value = false
    emit('refresh')
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    isSaving.value = false
  }
}

interface DetailField {
  label: string
  prop: string
  type?: 'select' | 'text' | 'date'
  options?: Array<{ label: string; value: string | number }>
}

const detailFields = computed<DetailField[]>(() => {
  if (!props.node) return []

  const base: DetailField[] = [
    { label: '名称', prop: 'name' },
    { label: '描述', prop: 'description' },
  ]

  switch (store.activeTab) {
    case 'world':
      return [
        ...base,
        { label: '世界类型', prop: 'world_type', type: 'select', options: WORLD_TYPE_OPTIONS },
        { label: '状态', prop: 'status', type: 'select', options: WORLD_STATUS_OPTIONS },
        { label: '创建时间', prop: 'created_at', type: 'date' },
      ]
    case 'building':
      return [
        ...base,
        { label: '建筑类型', prop: 'building_type', type: 'select', options: BUILDING_TYPE_OPTIONS },
        { label: '所属世界', prop: 'world_id', type: 'text' },
        { label: '状态', prop: 'status', type: 'select', options: BUILDING_STATUS_OPTIONS },
      ]
    case 'floor':
      return [
        ...base,
        { label: '楼层类型', prop: 'floor_type', type: 'select', options: FLOOR_TYPE_OPTIONS },
        { label: '所属建筑', prop: 'building_id', type: 'text' },
      ]
    case 'room':
      return [
        ...base,
        { label: '房间类型', prop: 'room_type', type: 'select', options: ROOM_TYPE_OPTIONS },
        { label: '所属楼层', prop: 'floor_id', type: 'text' },
      ]
    default:
      return base
  }
})
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="isEditing ? '编辑空间' : '空间详情'"
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
                {{ field.options.find((o: any) => o.value === editForm[field.prop])?.label || editForm[field.prop] }}
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
          <el-form-item label="名称">
            <el-input v-model="editForm.name" />
          </el-form-item>

          <el-form-item label="描述">
            <el-input v-model="editForm.description" type="textarea" :rows="3" />
          </el-form-item>

          <el-form-item
            v-for="field in detailFields.filter(f => f.type === 'select')"
            :key="field.prop"
            :label="field.label"
          >
            <el-select v-model="editForm[field.prop]" placeholder="请选择" style="width: 100%">
              <el-option
                v-for="opt in field.options"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-form>

        <div class="action-buttons">
          <el-button @click="handleCancel">取消</el-button>
          <el-button type="primary" :loading="isSaving" @click="handleSave">
            保存
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
