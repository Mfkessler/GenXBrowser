<template>
  <div class="relative inline-block w-full" ref="dropdownRoot">
    <button
      type="button"
      @click="toggleDropdown"
      :disabled="isDisabled"
      class="flex items-center justify-between w-full border border-gray-300 rounded-md p-2 text-left"
      :class="isDisabled ? 'cursor-not-allowed bg-gray-100 text-gray-400 opacity-70' : 'bg-white'"
    >
      <!-- Show the display value, not the key -->
      <!-- 🟢 Wenn kein Wert gewählt, zeige Placeholder -->
      <i :class="selectedDisplayValue ? 'text-gray-800' : 'text-gray-400 italic'">
        {{ selectedDisplayValue || placeholder }}
      </i>
      <svg
        class="w-5 h-5 ml-2 text-primary-900 transition-transform duration-300"
        viewBox="0 0 20 20"
        fill="currentColor"
        :class="{
          'rotate-180': isOpen,
          'opacity-50 cursor-not-allowed': isDisabled,
        }"
      >
        <path
          fill-rule="evenodd"
          d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
          clip-rule="evenodd"
        />
      </svg>
    </button>
    <transition name="fade">
      <div
        v-show="isOpen"
        class="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto"
      >
        <ul>
          <li
            v-for="key in optionKeys"
            :key="key"
            @click="selectOption(key)"
            class="cursor-pointer hover:bg-accent2-100 hover:shadow-md p-2 rounded-md hover:text-white"
          >
            <!-- Show the display value, not the key -->
            <i class="block truncate">{{ props.options[key] }}</i>
          </li>
        </ul>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  watch,
  nextTick,
  onBeforeUnmount,
  computed,
} from "vue";

const props = defineProps<{
  modelValue: string;
  options: Record<string | number, string | number>;
  placeholder?: string;
  disabled?: boolean;
}>();

const emit = defineEmits(["update:modelValue"]);

const selectedOption = ref<string>(props.modelValue || "");
const isOpen = ref(false);
const dropdownRoot = ref<HTMLElement | null>(null);

const optionKeys = computed(() => Object.keys(props.options));
const isDisabled = computed(() => props.disabled || optionKeys.value.length === 0);

const selectedDisplayValue = computed(() =>
  selectedOption.value ? props.options[selectedOption.value] : "",
);

const toggleDropdown = async () => {
  if (isDisabled.value) return;
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    await nextTick();
    document.addEventListener("click", onClickOutside, true);
  } else {
    document.removeEventListener("click", onClickOutside, true);
  }
};

const closeDropdown = () => {
  isOpen.value = false;
  document.removeEventListener("click", onClickOutside, true);
};

const selectOption = (key: string) => {
  selectedOption.value = key;
  emit("update:modelValue", key);
  closeDropdown();
};

function onClickOutside(event: MouseEvent) {
  if (!dropdownRoot.value) return;
  if (!dropdownRoot.value.contains(event.target as Node)) {
    closeDropdown();
  }
}

// Clean up
onBeforeUnmount(() => {
  document.removeEventListener("click", onClickOutside, true);
});

// Sync selectedOption if prop changes
watch(
  () => props.modelValue,
  (newVal) => {
    selectedOption.value = newVal;
  },
);
</script>
