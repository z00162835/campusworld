<template>
  <div class="entry-sequence">
    <div class="entry-title">CampusWorld</div>
    <div class="entry-steps">
      <span>{{ t('worldInteraction.entry.connecting') }}</span>
      <span>{{ t('worldInteraction.entry.restoring') }}</span>
      <span>{{ t('worldInteraction.entry.preparing') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.entry-sequence {
  min-height: calc(100vh - var(--header-height) - var(--tab-bar-height));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-lg);
}

.entry-title {
  font-size: 28px;
  font-weight: var(--font-weight-semibold);
}

.entry-steps {
  display: flex;
  gap: var(--spacing-lg);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

@media (max-width: 720px) {
  .entry-steps {
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-sm);
  }
}
</style>
