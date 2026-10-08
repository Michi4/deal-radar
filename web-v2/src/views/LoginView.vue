<template>
  <div class="loginwrap">
    <div class="panel">
      <h2>deal-radar login</h2>
      <p><small>Shared-password login for this deployment. Too many tries briefly locks you out — wait a minute, then try again.</small></p>
      <form @submit.prevent="doLogin">
        <input v-model="pw" class="inp" type="password" placeholder="password" aria-label="password" autocomplete="current-password" />
        <button class="btn btn-primary" type="submit">log in</button>
      </form>
      <div v-if="err" class="err">{{ err }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const pw = ref('');
const err = ref('');
const router = useRouter();
async function doLogin() {
  const r = await fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw.value }) });
  if (r.ok || r.redirected) router.push('/');
  else {
    try { err.value = (await r.json()).error || 'wrong password'; }
    catch { err.value = 'wrong password'; }
  }
}
</script>

<style scoped>
.loginwrap { max-width: 24rem; margin: 4rem auto; }
form { display: flex; flex-direction: column; gap: 0.625rem; }
.err { color: #dc2626; margin-top: 0.5rem; }
small { color: var(--mut); }
</style>
