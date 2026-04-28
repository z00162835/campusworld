<script setup lang="ts">
/**
 * RoomCard - Specialized card for Room nodes
 */
import SpaceCard from './SpaceCard.vue'
import type { Room } from '@/types/space'

defineProps<{
  node: Room
}>()

defineEmits<{
  click: [node: Room]
}>()
</script>

<template>
  <SpaceCard :node="node" type="room" />
</template>
