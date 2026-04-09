<script setup lang="ts">
import { ref, computed } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string
  label?: string
  type?: 'text' | 'password' | 'email'
  placeholder?: string
  error?: string
  disabled?: boolean
}>(), {
  type: 'text',
  placeholder: ''
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isFocused = ref(false)

const inputClasses = computed(() => ({
  'cyber-input': true,
  'cyber-input--focused': isFocused.value,
  'cyber-input--error': !!props.error,
  'cyber-input--disabled': props.disabled
}))

const handleInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  emit('update:modelValue', target.value)
}

const handleFocus = () => {
  if (!props.disabled) {
    isFocused.value = true
  }
}

const handleBlur = () => {
  isFocused.value = false
}
</script>

<template>
  <div :class="inputClasses">
    <label v-if="label" class="cyber-input__label">{{ label }}</label>
    <div class="cyber-input__wrapper">
      <input
        class="cyber-input__field"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        autocomplete="off"
        @input="handleInput"
        @focus="handleFocus"
        @blur="handleBlur"
      >
      <span v-if="isFocused && !error" class="cyber-input__cursor" />
    </div>
    <span v-if="error" class="cyber-input__error">{{ error }}</span>
  </div>
</template>

<style scoped>
.cyber-input {
  position: relative;
  margin-bottom: var(--spacing-lg);
}

.cyber-input__wrapper {
  position: relative;
  background: var(--cyber-bg-dark);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  transition: all var(--transition-glow);
}

.cyber-input__wrapper::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg,
    transparent,
    var(--cyber-primary) 20%,
    var(--cyber-primary) 80%,
    transparent);
  opacity: 0;
  transition: opacity var(--transition-glow);
}

.cyber-input--focused .cyber-input__wrapper {
  border-color: var(--cyber-primary);
  box-shadow: var(--glow-primary);
}

.cyber-input--focused .cyber-input__wrapper::before {
  opacity: 1;
}

.cyber-input--error .cyber-input__wrapper {
  border-color: var(--cyber-danger);
  box-shadow: 0 0 15px var(--cyber-danger-glow);
}

.cyber-input__label {
  display: block;
  font-family: var(--font-mono);
  font-size: var(--font-size-label);
  letter-spacing: var(--letter-spacing-wider);
  color: var(--cyber-text-dim);
  margin-bottom: var(--spacing-xs);
  text-transform: uppercase;
}

.cyber-input--focused .cyber-input__label {
  color: var(--cyber-primary);
  text-shadow: var(--glow-text);
}

.cyber-input__field {
  width: 100%;
  background: transparent;
  border: none;
  padding: var(--spacing-md) var(--spacing-sm);
  font-family: var(--font-mono);
  font-size: var(--font-size-mono);
  color: var(--cyber-text-bright);
  outline: none;
}

.cyber-input__field::placeholder {
  color: var(--cyber-text-dim);
  opacity: 0.6;
}

.cyber-input__cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  background: var(--cyber-primary);
  animation: cursor-blink 1s step-end infinite;
  vertical-align: middle;
  margin-left: 2px;
  position: absolute;
  right: var(--spacing-md);
  top: 50%;
  transform: translateY(-50%);
}

@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.cyber-input__error {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--cyber-danger);
  margin-top: var(--spacing-xs);
  letter-spacing: var(--letter-spacing-wide);
}

/* Error shake animation */
@keyframes error-shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-8px); }
  40%, 80% { transform: translateX(8px); }
}

.cyber-input--error .cyber-input__wrapper {
  animation: error-shake 0.3s ease;
}

.cyber-input--disabled .cyber-input__wrapper {
  opacity: 0.4;
  cursor: not-allowed;
}

.cyber-input--disabled .cyber-input__label {
  color: var(--text-disabled);
}

@media (prefers-reduced-motion: reduce) {
  .cyber-input__cursor {
    animation: none;
  }
  .cyber-input--error .cyber-input__wrapper {
    animation: none;
  }
}
</style>
