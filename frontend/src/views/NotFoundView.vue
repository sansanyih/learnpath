<script setup lang="ts">
</script>

<template>
  <div class="auth-shell" style="grid-template-columns:1fr">
    <main class="auth-right">
      <div class="auth-card" style="text-align:center">
        <div class="mono" style="color:var(--faint);letter-spacing:.14em">404 · NOT FOUND</div>
        <h2 style="margin-top:14px">这个页面不存在</h2>
        <p class="auth-sub">可能是链接过期了，或者地址写错了。</p>
        <router-link class="btn btn-primary" to="/" style="justify-content:center;width:100%">
          回到首页
        </router-link>
      </div>
    </main>
  </div>
</template>
