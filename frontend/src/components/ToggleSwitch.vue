<template>
  <div
    class="inline-block w-[60px] h-[30px] rounded-full bg-gray-300 relative cursor-pointer transition-colors duration-300 ease-in-out"
    :class="disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'"
    @click="toggle"
    role="checkbox"
    :aria-checked="modelValue ? 'true' : 'false'"
    :aria-disabled="disabled ? 'true' : 'false'"
    tabindex="0"
  >
    <div
      class="w-full h-full rounded-full transition-colors duration-300 ease-in-out"
      :class="{ 'bg-green-500': modelValue }"
    ></div>
    <div
      class="absolute w-[26px] h-[26px] bg-white rounded-full top-[2px] left-[2px] transition-transform duration-300 ease-in-out"
      :class="{ 'translate-x-[30px]': modelValue }"
    ></div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue"]);

const toggle = () => {
  if (props.disabled) return;
  emit("update:modelValue", !props.modelValue);
};
</script>
