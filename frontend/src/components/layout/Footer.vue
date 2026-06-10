<template>
  <div class="footer-content">
    <p>{{ t('shell.footerCopyright') }}</p>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.footer-content {
  text-align: center;
}
</style>
