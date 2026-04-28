<script setup lang="ts">
/**
 * WorldCard - Specialized card for World nodes
 */
import SpaceCard from './SpaceCard.vue'
import type { World } from '@/types/space'

const props = defineProps<{
  node: World
}>()

const emit = defineEmits<{
  click: [node: World]
}>()

const handleClick = () => {
  emit('click', props.node)
}
</script>

<template>
  <SpaceCard :node="node" type="world" @click="handleClick" />
</template>
