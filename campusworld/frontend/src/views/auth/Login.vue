<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ParticleBackground from '@/components/auth/ParticleBackground.vue'
import ScanlineOverlay from '@/components/auth/ScanlineOverlay.vue'
import BootSequence from '@/components/auth/BootSequence.vue'
import GlitchText from '@/components/auth/GlitchText.vue'
import SystemStatus from '@/components/auth/SystemStatus.vue'
import CyberInput from '@/components/auth/CyberInput.vue'
import CyberButton from '@/components/auth/CyberButton.vue'
import { useAuthStore, getAuthErrorMessage } from '@/stores/auth'
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
    errors.username = 'Username required'
    valid = false
  } else if (credentials.username.length < 3) {
    errors.username = 'Minimum 3 characters'
    valid = false
  } else {
    errors.username = ''
  }

  if (!credentials.password) {
    errors.password = 'Password required'
    valid = false
  } else if (credentials.password.length < 6) {
    errors.password = 'Minimum 6 characters'
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
    const success = await authStore.login(credentials)

    if (success) {
      // Mark boot sequence as shown for this session
      sessionStorage.setItem('boot_sequence_shown', 'true')
      // Redirect to safe destination only (validated redirect URL)
      const redirect = route.query.redirect as string | undefined
      const safeRedirect = isValidRedirect(redirect)
      router.push(safeRedirect || '/works')
    }
  } catch (error: any) {
    // Clear password on failure for security
    credentials.password = ''

    // Get HTTP status code
    const status = error.response?.status || 0

    // Only show safe, pre-defined error messages - never expose raw server details
    // This prevents information leakage about server internals
    const i18nKey = getAuthErrorMessage(status)
    authError.value = status === 0
      ? t('auth.errors.networkError')
      : t(i18nKey)
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
        <SystemStatus status="online" label="SYSTEM ONLINE" />
      </div>

      <!-- Login Form -->
      <form class="auth-form" @submit.prevent="handleLogin">
        <div class="form-group">
          <CyberInput
            v-model="credentials.username"
            label="USERNAME"
            placeholder="Enter identifier..."
            :error="errors.username"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <CyberInput
            v-model="credentials.password"
            label="PASSWORD"
            type="password"
            placeholder="Enter passphrase..."
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
          label="AUTHENTICATE"
          :loading="loading"
          :disabled="!isFormValid"
          size="large"
          class="auth-submit"
          @click="handleLogin"
        />

        <!-- Register Link -->
        <div class="auth-footer">
          <span class="auth-footer__text">New to CampusWorld?</span>
          <a href="/register" class="auth-link">CREATE ACCOUNT</a>
        </div>
      </form>
    </div>

    <!-- Version Info -->
    <div class="auth-version">
      <span>CAMPUSWORLD OS v{{ appVersion }}</span>
    </div>
  </div>
</template>

<style scoped>
.auth-container {
  position: relative;
  width: 100vw;
  height: 100vh;
  min-height: 100vh;
  background: linear-gradient(135deg, var(--cyber-bg-dark) 0%, var(--cyber-bg-mid) 50%, var(--cyber-bg-dark) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.auth-particles {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.auth-scanlines {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}

.grid-background {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--cyber-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--cyber-grid) 1px, transparent 1px);
  background-size: 50px 50px;
  pointer-events: none;
  z-index: 1;
}

.vignette-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 3;
  background: radial-gradient(
    ellipse at center,
    transparent 0%,
    transparent 60%,
    rgba(0, 0, 0, 0.4) 100%
  );
}

.auth-panel {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 420px;
  padding: var(--spacing-3xl);
  background: rgba(10, 10, 15, 0.85);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(10px);
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.auth-panel--visible {
  opacity: 1;
  transform: translateY(0);
}

.auth-decoration .corner {
  position: absolute;
  width: 20px;
  height: 20px;
  border-color: var(--cyber-primary);
  border-style: solid;
  border-width: 0;
}

.auth-decoration .corner--top-left {
  top: -1px;
  left: -1px;
  border-top-width: 2px;
  border-left-width: 2px;
}

.auth-decoration .corner--top-right {
  top: -1px;
  right: -1px;
  border-top-width: 2px;
  border-right-width: 2px;
}

.auth-decoration .corner--bottom-left {
  bottom: -1px;
  left: -1px;
  border-bottom-width: 2px;
  border-left-width: 2px;
}

.auth-decoration .corner--bottom-right {
  bottom: -1px;
  right: -1px;
  border-bottom-width: 2px;
  border-right-width: 2px;
}

.auth-header {
  text-align: center;
  margin-bottom: var(--spacing-2xl);
}

.auth-logo {
  font-family: var(--font-display);
  font-size: var(--font-size-display);
  font-weight: 700;
  letter-spacing: var(--letter-spacing-wider);
  color: var(--cyber-text-bright);
  text-shadow: var(--glow-text);
  margin: 0 0 var(--spacing-md);
}

.auth-form {
  display: flex;
  flex-direction: column;
}

.form-group {
  margin-bottom: var(--spacing-sm);
}

.auth-submit {
  margin-top: var(--spacing-lg);
  width: 100%;
}

.auth-error {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: rgba(255, 51, 102, 0.1);
  border: 1px solid var(--cyber-danger);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-md);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--cyber-danger);
}

.auth-error__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--cyber-danger);
  border-radius: 50%;
  color: white;
  font-weight: bold;
  font-size: 12px;
  flex-shrink: 0;
}

.auth-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xl);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.auth-footer__text {
  color: var(--cyber-text-dim);
}

.auth-link {
  color: var(--cyber-primary);
  text-decoration: none;
  letter-spacing: var(--letter-spacing-wide);
  transition: all var(--transition-glow);
}

.auth-link:hover {
  text-shadow: var(--glow-text);
}

.auth-version {
  position: fixed;
  bottom: var(--spacing-lg);
  right: var(--spacing-xl);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--cyber-text-dim);
  letter-spacing: var(--letter-spacing-wide);
  z-index: 10;
}

@media (max-width: 480px) {
  .auth-panel {
    margin: var(--spacing-md);
    padding: var(--spacing-xl);
  }

  .auth-logo {
    font-size: 24px;
  }
}
</style>
