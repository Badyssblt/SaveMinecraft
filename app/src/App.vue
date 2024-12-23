<script setup>
import { onMounted, ref } from "vue";

const status = ref("");

const runPython = () => {
  window.electron.runPythonScript();
}

onMounted(() => {
  window.electron.onPythonOutput((event, output) => {

    const parsedOutput = JSON.parse(output)
    
    status.value = parsedOutput.status;    
    
  });
})
</script>

<template>
  <button @click="runPython">Lancer le script</button>

  <p>{{ status }}</p>
</template>

