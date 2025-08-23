<template>
  <div id="app">
    <el-container class="app-container">
      <el-header class="app-header">
        <nav-bar />
      </el-header>
      
      <el-main class="app-main">
        <router-view />
      </el-main>
      
      <el-footer class="app-footer">
        <footer-component />
      </el-footer>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import NavBar from '@/components/layout/NavBar.vue'
import FooterComponent from '@/components/layout/Footer.vue'
</script>

<style scoped>
.app-container {
  min-height: 100vh;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0;
}

.app-main {
  flex: 1;
  padding: 20px;
  background: #f5f7fa;
}

.app-footer {
  background: #545c64;
  color: #fff;
  text-align: center;
  padding: 20px;
}
</style>
