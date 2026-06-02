<template>
  <!--
    GAIA (GenXBrowser AI-Assistant) mark: a gene double-helix rung ladder
    paired with an AI sparkle. Drawn with currentColor so it inherits the
    surrounding text colour and stays crisp/themeable at any size.
  -->
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <!-- Two helix strands sweeping top-left to bottom-left -->
    <path d="M6.5 3c0 4.5 7 5.5 7 9s-7 4.5-7 9" />
    <path d="M13.5 3c0 4.5-7 5.5-7 9s7 4.5 7 9" />
    <!-- Base-pair rungs -->
    <path d="M7.4 6.2h5.2" />
    <path d="M6.6 12h6.8" />
    <path d="M7.4 17.8h5.2" />
    <!-- AI sparkle accent, top-right -->
    <path
      fill="currentColor"
      stroke="none"
      d="M18.5 2.5l.7 2.1q.16.5.66.66l2.1.7-2.1.7q-.5.16-.66.66l-.7 2.1-.7-2.1q-.16-.5-.66-.66l-2.1-.7 2.1-.7q.5-.16.66-.66z"
    />
  </svg>
</template>
