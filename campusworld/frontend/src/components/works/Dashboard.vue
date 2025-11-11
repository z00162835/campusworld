<template>
  <div class="dashboard-section">
    <div class="section-header">
      <h3 class="section-title">Dashboard</h3>
    </div>
    <div class="dashboard-grid">
      <div class="dashboard-card">
        <div class="card-icon">
          <el-icon :size="24"><Document /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">12</div>
          <div class="card-label">Active Projects</div>
        </div>
      </div>
      <div class="dashboard-card">
        <div class="card-icon">
          <el-icon :size="24"><User /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">8</div>
          <div class="card-label">Active Agents</div>
        </div>
      </div>
      <div class="dashboard-card">
        <div class="card-icon">
          <el-icon :size="24"><Clock /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">24</div>
          <div class="card-label">Tasks Today</div>
        </div>
      </div>
      <div class="dashboard-card">
        <div class="card-icon">
          <el-icon :size="24"><Check /></el-icon>
        </div>
        <div class="card-content">
          <div class="card-value">18</div>
          <div class="card-label">Completed</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Document, User, Clock, Check } from '@element-plus/icons-vue'
</script>

<style scoped>
.dashboard-section {
  margin-bottom: var(--spacing-2xl);
}

.section-header {
  margin-bottom: var(--spacing-lg);
}

.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-lg);
}

.dashboard-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  transition: all var(--transition-fast);
}

.dashboard-card:hover {
  border-color: var(--border-color-dark);
  background: var(--bg-secondary);
}

.card-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  color: var(--color-primary);
  flex-shrink: 0;
}

.card-content {
  flex: 1;
}

.card-value {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: 1.2;
  margin-bottom: var(--spacing-xs);
}

.card-label {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
</style>

