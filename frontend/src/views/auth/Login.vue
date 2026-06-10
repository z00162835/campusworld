<script setup lang="ts">
import { ref, reactive, computed, onMounted, defineAsyncComponent } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

// Dynamic imports for heavy animation components (reduce initial bundle)
const ParticleBackground = defineAsyncComponent(() =>
  import('@/components/auth/ParticleBackground.vue')
)
const ScanlineOverlay = defineAsyncComponent(() =>
  import('@/components/auth/ScanlineOverlay.vue')
)
const BootSequence = defineAsyncComponent(() =>
  import('@/components/auth/BootSequence.vue')
)
const GlitchText = defineAsyncComponent(() =>
  import('@/components/auth/GlitchText.vue')
)
const SystemStatus = defineAsyncComponent(() =>
  import('@/components/auth/SystemStatus.vue')
)
import CyberInput from '@/components/auth/CyberInput.vue'
import CyberButton from '@/components/auth/CyberButton.vue'
import { getAuthErrorMessage, useAuthStore } from '@/stores/auth'
import { isValidRedirect } from '@/router'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// Boot sequence control - only show once per session
const showBootSequence = ref(true)
const showLoginForm = ref(false)

// Check if boot sequence was already shown this session
onMounted(() => {
  const hasSeenBoot = sessionStorage.getItem('boot_sequence_shown')
  if (hasSeenBoot) {
    showBootSequence.value = false
    showLoginForm.value = true
  }
})

const credentials = reactive({
  username: '',
  password: ''
})

const errors = reactive({
  username: '',
  password: ''
})

const loading = ref(false)
const authError = ref('')

const isFormValid = computed(() => {
  return credentials.username.length >= 3 && credentials.password.length >= 6
})

const validateForm = (): boolean => {
  let valid = true

  if (!credentials.username) {
    errors.username = t('auth.validation.usernameRequired')
    valid = false
  } else if (credentials.username.length < 3) {
    errors.username = t('auth.validation.usernameMin')
    valid = false
  } else {
    errors.username = ''
  }

  if (!credentials.password) {
    errors.password = t('auth.validation.passwordRequired')
    valid = false
  } else if (credentials.password.length < 6) {
    errors.password = t('auth.validation.passwordMin')
    valid = false
  } else {
    errors.password = ''
  }

  return valid
}

const handleLogin = async () => {
  authError.value = ''

  if (!validateForm()) return

  loading.value = true

  try {
    const result = await authStore.login(credentials)

    if (result.success) {
      // Mark boot sequence as shown for this session
      sessionStorage.setItem('boot_sequence_shown', 'true')
      // Redirect to safe destination only (validated redirect URL)
      const redirect = route.query.redirect as string | undefined
      const safeRedirect = isValidRedirect(redirect)
      router.push(safeRedirect || '/works')
    } else {
      credentials.password = ''
      authError.value = result.status === 0
        ? t('auth.errors.networkError')
        : t(getAuthErrorMessage(result.status || 0))
    }
  } catch (error: any) {
    // Clear password on failure for security
    credentials.password = ''
    authError.value = t('auth.errors.invalidCredentials')
  } finally {
    loading.value = false
  }
}

const onBootComplete = () => {
  sessionStorage.setItem('boot_sequence_shown', 'true')
  showBootSequence.value = false
  showLoginForm.value = true
}

const appVersion = import.meta.env.VITE_APP_VERSION || '1.0.0'
</script>

<template>
  <div class="auth-container">
    <!-- Background Effects Layer -->
    <ParticleBackground class="auth-particles" />
    <ScanlineOverlay class="auth-scanlines" />

    <!-- Grid Background -->
    <div class="grid-background" />

    <!-- Vignette Effect -->
    <div class="vignette-overlay" />

    <!-- Boot Sequence Overlay -->
    <BootSequence
      v-if="showBootSequence"
      :duration="2500"
      @complete="onBootComplete"
    />

    <!-- Main Auth Panel -->
    <div class="auth-panel" :class="{ 'auth-panel--visible': showLoginForm }">
      <!-- Corner Decorations -->
      <div class="auth-decoration">
        <div class="corner corner--top-left" />
        <div class="corner corner--top-right" />
        <div class="corner corner--bottom-left" />
        <div class="corner corner--bottom-right" />
      </div>

      <!-- Logo Section -->
      <div class="auth-header">
        <GlitchText
          text="CAMPUSWORLD"
          tag="h1"
          intensity="low"
          trigger="continuous"
          class="auth-logo"
        />
        <SystemStatus status="online" :label="t('auth.systemOnline')" />
      </div>

      <!-- Login Form -->
      <form class="auth-form" @submit.prevent="handleLogin">
        <div class="form-group">
          <CyberInput
            v-model="credentials.username"
            :label="t('auth.usernameLabel')"
            :placeholder="t('auth.usernamePlaceholder')"
            :error="errors.username"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <CyberInput
            v-model="credentials.password"
            :label="t('auth.passwordLabel')"
            type="password"
            :placeholder="t('auth.passwordPlaceholder')"
            :error="errors.password"
            :disabled="loading"
          />
        </div>

        <!-- Error Display -->
        <div v-if="authError" class="auth-error">
          <span class="auth-error__icon">!</span>
          <span>{{ authError }}</span>
        </div>

        <!-- Submit Button -->
        <CyberButton
          :label="t('auth.authenticate')"
          :loading="loading"
          :disabled="loading || !isFormValid"
          size="large"
          class="auth-submit"
          @click="handleLogin"
        />

        <!-- Register Link -->
        <div class="auth-footer">
          <span class="auth-footer__text">{{ t('auth.loginPrompt') }}</span>
          <router-link to="/register" class="auth-link">{{ t('auth.createAccount') }}</router-link>
        </div>
      </form>
    </div>

    <!-- Version Info -->
    <div class="auth-version">
      <span>CAMPUSWORLD OS v{{ appVersion }}</span>
    </div>
  </div>
</template>
