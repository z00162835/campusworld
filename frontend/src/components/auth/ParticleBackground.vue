<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  color: string
}

const props = withDefaults(defineProps<{
  particleCount?: number
  connectionDistance?: number
  particleColor?: string
}>(), {
  particleCount: 80,
  connectionDistance: 120,
  particleColor: '#00f5ff'
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationId: number | null = null
let particles: Particle[] = []
let mouseX = -1000
let mouseY = -1000

const isMobile = computed(() => {
  if (typeof window === 'undefined') return false
  return window.innerWidth < 768
})

const getParticleCount = () => {
  if (isMobile.value) return Math.floor(props.particleCount * 0.5)
  return props.particleCount
}

const initParticles = (canvas: HTMLCanvasElement) => {
  const count = getParticleCount()
  particles = []

  for (let i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      radius: Math.random() * 2 + 1,
      color: props.particleColor
    })
  }
}

const draw = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
  ctx.clearRect(0, 0, width, height)

  // Update and draw particles
  for (const particle of particles) {
    // Mouse interaction - subtle repulsion
    const dx = particle.x - mouseX
    const dy = particle.y - mouseY
    const dist = Math.sqrt(dx * dx + dy * dy)

    if (dist < 100) {
      const force = (100 - dist) / 100
      particle.vx += (dx / dist) * force * 0.2
      particle.vy += (dy / dist) * force * 0.2
    }

    // Apply velocity with damping
    particle.x += particle.vx
    particle.y += particle.vy
    particle.vx *= 0.99
    particle.vy *= 0.99

    // Boundary wrapping
    if (particle.x < 0) particle.x = width
    if (particle.x > width) particle.x = 0
    if (particle.y < 0) particle.y = height
    if (particle.y > height) particle.y = 0

    // Draw particle
    ctx.beginPath()
    ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2)
    ctx.fillStyle = particle.color
    ctx.globalAlpha = 0.6
    ctx.fill()
    ctx.globalAlpha = 1
  }

  // Draw connections
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const p1 = particles[i]
      const p2 = particles[j]
      const dx = p1.x - p2.x
      const dy = p1.y - p2.y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist < props.connectionDistance) {
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.lineTo(p2.x, p2.y)
        ctx.strokeStyle = props.particleColor
        ctx.globalAlpha = (1 - dist / props.connectionDistance) * 0.3
        ctx.lineWidth = 0.5
        ctx.stroke()
        ctx.globalAlpha = 1
      }
    }
  }
}

const animate = () => {
  if (!canvasRef.value) return
  const ctx = canvasRef.value.getContext('2d')
  if (!ctx) return

  draw(ctx, canvasRef.value.width, canvasRef.value.height)
  animationId = requestAnimationFrame(animate)
}

const handleResize = () => {
  if (!canvasRef.value) return
  canvasRef.value.width = window.innerWidth
  canvasRef.value.height = window.innerHeight
  initParticles(canvasRef.value)
}

const handleMouseMove = (e: MouseEvent) => {
  mouseX = e.clientX
  mouseY = e.clientY
}

const handleMouseLeave = () => {
  mouseX = -1000
  mouseY = -1000
}

onMounted(() => {
  if (!canvasRef.value) return

  canvasRef.value.width = window.innerWidth
  canvasRef.value.height = window.innerHeight
  initParticles(canvasRef.value)
  animate()

  window.addEventListener('resize', handleResize)
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseleave', handleMouseLeave)
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseleave', handleMouseLeave)
})
</script>

<template>
  <canvas
    ref="canvasRef"
    class="particle-background"
  />
</template>

<style scoped>
.particle-background {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, var(--cyber-bg-dark) 0%, var(--cyber-bg-mid) 100%);
  will-change: transform;
  contain: layout style paint;
}
</style>
