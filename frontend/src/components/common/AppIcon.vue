<template>
  <el-icon
    class="app-icon"
    :class="props.iconClass"
    :style="sizeStyle"
    :aria-hidden="decorative ? 'true' : undefined"
  >
    <component :is="iconComponent" />
  </el-icon>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getIconComponent, type IconName } from '@/icons'

const props = withDefaults(
  defineProps<{
    name: IconName
    size?: number
    iconClass?: string
    decorative?: boolean
  }>(),
  {
    size: 16,
    decorative: true,
  },
)

const iconComponent = computed(() => getIconComponent(props.name))
const sizeStyle = computed(() => ({ fontSize: `${props.size}px` }))
</script>

<style scoped>
.app-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  flex-shrink: 0;
}
</style>
