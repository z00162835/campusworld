<template>
  <slot v-if="!error" />
  <div v-else class="error-boundary">
    <el-result
      icon="error"
      :title="t('errorBoundary.title')"
      :sub-title="t('errorBoundary.subtitle')"
    >
      <template #extra>
        <el-button type="primary" @click="reset">{{ t('common.retry') }}</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useI18n } from 'vue-i18n'

const error = ref<Error | null>(null)
const { t } = useI18n()

onErrorCaptured((err) => {
  error.value = err
  return false
})

const reset = () => {
  error.value = null
}
</script>

<style scoped>
.error-boundary {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}
</style>
