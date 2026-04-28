<script setup lang="ts">
/**
 * BuildingCard - Specialized card for Building nodes
 */
import SpaceCard from './SpaceCard.vue'
import type { Building } from '@/types/space'

defineProps<{
  node: Building
}>()

defineEmits<{
  click: [node: Building]
}>()
</script>

<template>
  <SpaceCard :node="node" type="building" />
</template>
