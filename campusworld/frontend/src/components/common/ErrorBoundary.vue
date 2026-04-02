<template>
  <slot v-if="!error" />
  <div v-else class="error-boundary">
    <el-result
      icon="error"
      title="出错了"
      sub-title="抱歉，应用遇到了一些问题"
    >
      <template #extra>
        <el-button type="primary" @click="reset">重试</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const error = ref<Error | null>(null)

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
