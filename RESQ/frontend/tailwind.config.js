/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // A named type scale for this dashboard's information density,
      // replacing what had become eight slightly-different arbitrary
      // pixel values (10px, 10.5px, 11px, 11.5px, 12px, 12.5px, 13px,
      // 15px) scattered ad hoc across components. Five deliberate steps.
      fontSize: {
        "2xs": ["10px", { lineHeight: "14px" }], // micro labels, chip counts
        xs: ["11px", { lineHeight: "15px" }], // secondary text, metadata
        sm: ["12.5px", { lineHeight: "17px" }], // primary body copy
        base: ["13px", { lineHeight: "18px" }], // panel titles, emphasis
        lg: ["15px", { lineHeight: "20px" }], // page title
      },
      // Restrained elevation — one step, used sparingly for panels and
      // popovers so depth reads as structure, not glassmorphism.
      boxShadow: {
        panel: "0 1px 2px rgb(0 0 0 / 0.28), 0 1px 1px rgb(0 0 0 / 0.16)",
        raised: "0 4px 12px rgb(0 0 0 / 0.35), 0 2px 4px rgb(0 0 0 / 0.2)",
      },
    },
  },
  plugins: [],
};
