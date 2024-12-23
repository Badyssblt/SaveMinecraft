<script setup>
import { onMounted, ref } from "vue";
import BottomBar from "./components/BottomBar.vue"

const status = ref("");
const type = ref('curseforge');

const runPython = () => {
  window.electron.runPythonScript(type.value)
}

onMounted(() => {
  window.electron.onPythonOutput((event, output) => {

    const parsedOutput = JSON.parse(output)
    
    status.value = parsedOutput.status;    
    
  });
})
</script>

<template>
  <div class="p-4">
    <h2 class="text-xl text-medium mb-6">Cloud Minecraft</h2>

    <form @submit.prevent="runPython" class="flex flex-col items-start">
      <select name="type" id="type" v-model="type">
        <option value="vanilla">Minecraft Vanilla</option>
        <option value="curseforge">Minecraft moddée (Curseforge)</option>
      </select>

      <button type="submit" class="bg-green-700 px-6 py-2 text-white rounded mt-4">Lancer le script</button>

    </form>

    <div class="mt-6">
      <h3 class="text-lg font-medium">Tous mes mondes</h3>
    </div>

    <p>{{ status }}</p>
  </div>
  <BottomBar/>
</template>

