<template>
  <div class="history-page">
    <el-card>
      <template #header>
        <div class="page-header">
          <h2>{{ t('routes.history') }}</h2>
        </div>
      </template>
      <p class="page-description">{{ t('placeholderPages.historyDescription') }}</p>
      <el-alert
        :title="t('common.inDevelopment')"
        type="info"
        :closable="false"
        class="page-alert"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.history-page {
  padding: 0;
}

.page-header h2 {
  margin: 0;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.page-description {
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  margin: var(--spacing-md) 0;
}

.page-alert {
  margin-top: var(--spacing-xl);
}
</style>
