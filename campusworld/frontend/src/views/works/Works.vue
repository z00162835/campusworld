<template>
  <div class="works-page">
    <el-card>
      <template #header>
        <div class="page-header">
          <h2>Works</h2>
        </div>
      </template>
      <p class="page-description">工作区管理页面</p>
      <el-alert
        title="功能开发中"
        type="info"
        :closable="false"
        class="page-alert"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.works-page {
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

