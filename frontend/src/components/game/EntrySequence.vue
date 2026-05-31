<template>
  <div class="entry-sequence">
    <div class="entry-title">CampusWorld</div>
    <div class="entry-steps">
      <span>Connecting semantic world</span>
      <span>Restoring last location</span>
      <span>Preparing decisions</span>
    </div>
  </div>
</template>

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
