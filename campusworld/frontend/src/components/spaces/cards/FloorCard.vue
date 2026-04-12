<script setup lang="ts">
/**
 * FloorCard - Specialized card for Floor nodes
 */
import SpaceCard from './SpaceCard.vue'
import type { Floor } from '@/types/space'

defineProps<{
  node: Floor
}>()

defineEmits<{
  click: [node: Floor]
}>()
</script>

<template>
  <SpaceCard :node="node" type="floor" />
</template>
